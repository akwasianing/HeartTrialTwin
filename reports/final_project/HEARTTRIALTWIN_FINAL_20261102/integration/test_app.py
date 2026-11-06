"""Offline Streamlit rendering and bounded worker error handling."""
import json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP=Path(__file__).with_name('app.py')

class AppTests(unittest.TestCase):
    def app(self):return AppTest.from_file(str(APP),default_timeout=15).run()

    def test_startup_warning_and_fields(self):
        a=self.app();self.assertFalse(a.exception);self.assertIn('clinical decision',a.warning[0].value)
        self.assertEqual(a.text_input[0].value,'NCT00206232')

    def test_discovery_shows_registered_filters(self):
        a=self.app();a.radio[0].set_value('Phase and intervention discovery').run()
        self.assertFalse(a.exception);self.assertIn('NA',a.selectbox[0].options);self.assertIn('DEVICE',a.selectbox[1].options)

    def test_analysis_figures_and_table(self):
        a=self.app();a.radio[0].set_value('Verified descriptive results').run()
        self.assertFalse(a.exception);self.assertEqual(len(a.dataframe),1)

    def test_models_labeled_exploratory(self):
        a=self.app();a.radio[0].set_value('Exploratory historical modeling').run()
        self.assertFalse(a.exception);self.assertIn('not an independent',a.info[0].value.lower())

    def test_worker_timeout_abstains(self):
        a=self.app()
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('redacted-local-worker',60)):
            a.button[0].click().run()
        self.assertFalse(a.exception);self.assertTrue(any('timed out' in t.value for t in a.text))

    def test_worker_failure_does_not_print_stderr(self):
        a=self.app()
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],1,'','PRIVATE_DIAGNOSTIC_NOT_FOR_UI')):
            a.button[0].click().run()
        self.assertFalse(a.exception);self.assertTrue(any('Evidence verification failed' in t.value for t in a.text))
        self.assertFalse(any('PRIVATE_DIAGNOSTIC' in t.value for t in a.text))


if __name__=='__main__':unittest.main()
