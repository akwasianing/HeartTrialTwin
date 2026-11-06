"""Small contact sheet for visual QA only; never changes source figures."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

p=Path(__file__).resolve().parent
files=sorted((p/'figures').glob('*.png'))
im=Image.new('RGB',(1800,440*((len(files)+2)//3)),'#DCE4E8');d=ImageDraw.Draw(im)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
for i,f in enumerate(files):
    x=(i%3)*600;y=(i//3)*440
    with Image.open(f) as picture:
        picture.thumbnail((580,370));im.paste(picture,(x+10,y+35))
    d.text((x+10,y+8),f.stem,font=font,fill='#122B45')
im.save(p/'_build/figure_contact_sheet.png')
print(len(files),'figure pairs')
