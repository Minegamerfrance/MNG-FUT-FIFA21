"""Server-rendered countdown; preserve the supplied poster on disk."""
from functools import lru_cache
from io import BytesIO
from PIL import Image,ImageDraw,ImageFont

def remaining(deadline,now):
    seconds=max(0,int(deadline)-int(now))
    days,seconds=divmod(seconds,86400)
    hours,seconds=divmod(seconds,3600)
    minutes,seconds=divmod(seconds,60)
    return days,hours,minutes,seconds

@lru_cache(maxsize=2)
def render(poster,parts):
    with Image.open(BytesIO(poster)) as source:
        image=source.convert('RGBA')
    width,height=image.size
    sx,sy=width/1920,height/1080
    overlay=Image.new('RGBA',image.size)
    draw=ImageDraw.Draw(overlay)
    box=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate((395,870,1490,1050)))
    draw.rounded_rectangle(box,radius=round(20*sx),fill=(9,8,18,225),outline=(220,35,210,255),width=max(1,round(2*sx)))
    def text(x,y,value,size,fill):
        font=ImageFont.load_default(size=max(12,round(size*sx)))
        draw.text((round(x*sx),round(y*sy)),value,font=font,fill=fill,anchor='mm')
    for index,value in enumerate(parts):
        x=395+(index+.5)*(1490-395)/4
        text(x,960,f'{value:02d}',64,(199,255,35,255))
    image=Image.alpha_composite(image,overlay).convert('RGB')
    output=BytesIO();image.save(output,format='JPEG',quality=92)
    return output.getvalue()
