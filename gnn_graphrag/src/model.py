"""Small CPU-only mean-aggregation GraphSAGE for HeartTrialTwin."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


DEFAULT_SEED = 20261022
INPUT_DIMENSION = 390
HIDDEN_DIMENSION = 128
OUTPUT_DIMENSION = 64


class ModelError(RuntimeError):
    """Raised when a GraphSAGE input violates the model contract."""


def configure_determinism(seed: int = DEFAULT_SEED) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ModelError("seed must be an integer")
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def mean_aggregate(node_features: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
    """Mean incoming source features for each target; isolates receive zeros."""

    if node_features.ndim != 2:
        raise ModelError("node_features must have shape [nodes, features]")
    if edge_index.ndim != 2 or edge_index.shape[0] != 2:
        raise ModelError("edge_index must have shape [2, edges]")
    if edge_index.dtype != torch.long:
        raise ModelError("edge_index must use torch.long")
    node_count = node_features.shape[0]
    if edge_index.numel() and (int(edge_index.min()) < 0 or int(edge_index.max()) >= node_count):
        raise ModelError("edge_index contains an invalid node index")

    aggregated = torch.zeros_like(node_features)
    degrees = torch.zeros(node_count, dtype=node_features.dtype, device=node_features.device)
    if edge_index.shape[1] == 0:
        return aggregated
    sources, targets = edge_index
    aggregated.index_add_(0, targets, node_features[sources])
    degrees.index_add_(
        0,
        targets,
        torch.ones(targets.shape[0], dtype=node_features.dtype, device=node_features.device),
    )
    nonzero = degrees > 0
    aggregated[nonzero] = aggregated[nonzero] / degrees[nonzero].unsqueeze(1)
    return aggregated


class MeanGraphSAGELayer(nn.Module):
    """GraphSAGE mean layer: W [self || mean(neighbors)] + bias."""

    def __init__(self, input_dimension: int, output_dimension: int) -> None:
        super().__init__()
        self.input_dimension = input_dimension
        self.output_dimension = output_dimension
        self.linear = nn.Linear(input_dimension * 2, output_dimension)

    def forward(self, node_features: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        if node_features.shape[1] != self.input_dimension:
            raise ModelError(
                f"Expected {self.input_dimension} input features; found {node_features.shape[1]}"
            )
        neighbors = mean_aggregate(node_features, edge_index)
        return self.linear(torch.cat((node_features, neighbors), dim=1))


@dataclass(frozen=True)
class LayerRepresentations:
    layer0: torch.Tensor
    layer1: torch.Tensor
    layer2: torch.Tensor


class TwoLayerGraphSAGE(nn.Module):
    def __init__(
        self,
        input_dimension: int = INPUT_DIMENSION,
        hidden_dimension: int = HIDDEN_DIMENSION,
        output_dimension: int = OUTPUT_DIMENSION,
    ) -> None:
        super().__init__()
        self.input_dimension = input_dimension
        self.hidden_dimension = hidden_dimension
        self.output_dimension = output_dimension
        self.layer1 = MeanGraphSAGELayer(input_dimension, hidden_dimension)
        self.layer2 = MeanGraphSAGELayer(hidden_dimension, output_dimension)

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> LayerRepresentations:
        if node_features.ndim != 2 or node_features.shape[1] != self.input_dimension:
            raise ModelError(
                f"Expected [nodes, {self.input_dimension}] node features; found {tuple(node_features.shape)}"
            )
        layer1 = F.relu(self.layer1(node_features, edge_index))
        layer2 = F.relu(self.layer2(layer1, edge_index))
        return LayerRepresentations(node_features, layer1, layer2)


def build_seeded_model(seed: int = DEFAULT_SEED) -> TwoLayerGraphSAGE:
    configure_determinism(seed)
    model = TwoLayerGraphSAGE()
    model.eval()
    return model


def model_state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        encoded_name = name.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        shape = str(tuple(value.shape)).encode("ascii")
        digest.update(len(shape).to_bytes(8, "big"))
        digest.update(shape)
        canonical = value.detach().cpu().contiguous().numpy().astype("<f4", copy=False)
        digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def tensor_sha256(value: torch.Tensor) -> str:
    canonical = value.detach().cpu().contiguous().numpy().astype("<f4", copy=False)
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def within_space_diagnostics(reference: torch.Tensor, comparison: torch.Tensor) -> dict[str, Any]:
    """Compare vectors only when they occupy the same representation space."""

    if reference.ndim != 1 or comparison.ndim != 1 or reference.shape != comparison.shape:
        raise ModelError("Diagnostics require same-shape one-dimensional vectors")
    ref_norm = float(torch.linalg.vector_norm(reference))
    comparison_norm = float(torch.linalg.vector_norm(comparison))
    delta = reference - comparison
    delta_norm = float(torch.linalg.vector_norm(delta))
    if ref_norm == 0.0 or comparison_norm == 0.0:
        cosine = None
    else:
        cosine = float(F.cosine_similarity(reference.unsqueeze(0), comparison.unsqueeze(0)).item())
    return {
        "dimension": int(reference.shape[0]),
        "reference_norm": ref_norm,
        "comparison_norm": comparison_norm,
        "l2_difference": delta_norm,
        "relative_l2_difference_to_reference": None if ref_norm == 0.0 else delta_norm / ref_norm,
        "cosine_similarity_same_space": cosine,
    }
