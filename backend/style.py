"""Bounded template and narration settings shared by the assistant and renderer."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Layout(BaseModel):
    font: Literal['bold', 'condensed', 'serif'] = 'bold'
    title_color: str = 'FFFFFF'
    rank_color: str = 'CAFA63'
    caption_color: str = 'FFFFFF'
    title_y: float = Field(default=0.0615, ge=0.01, le=0.35)
    title_size: float = Field(default=0.0454, ge=0.02, le=0.085)
    title_align: Literal['left', 'center', 'right'] = 'center'
    title_x: float = Field(default=.05, ge=.01, le=.75)
    rank_x: float = Field(default=0.0602, ge=0.01, le=0.8)
    rank_y: float = Field(default=0.1719, ge=0.05, le=0.65)
    rank_size: float = Field(default=0.1343, ge=0.05, le=0.24)
    caption_y: float = Field(default=0.7708, ge=0.45, le=0.9)
    caption_size: float = Field(default=0.0528, ge=0.025, le=0.09)
    caption_align: Literal['left', 'center', 'right'] = 'center'
    caption_x: float = Field(default=.07, ge=.01, le=.75)
    header_darkness: float = Field(default=0.5, ge=0, le=0.9)
    show_label: bool = True
    show_criteria: bool = True

    @field_validator('title_color', 'rank_color', 'caption_color')
    @classmethod
    def hex_color(cls, value):
        import re
        value = value.removeprefix('#').upper()
        if not re.fullmatch(r'[A-F0-9]{6}', value):
            raise ValueError('Barva musí být šestimístný HEX kód.')
        return value


class VoiceSettings(BaseModel):
    provider: Literal['openai', 'elevenlabs', 'piper'] = 'openai'
    voice: Literal['onyx', 'echo', 'adam', 'josh', 'antoni', 'custom', 'local'] = Field(default='onyx', validate_default=True)
    speed: float = Field(default=1.0, ge=0.85, le=1.2)
    delivery: str = Field(default='A confident, natural male narrator. Clear English, conversational energy, varied emphasis. No exaggerated shouting. Let the key observation land.', max_length=300)

    @field_validator('voice')
    @classmethod
    def compatible(cls, value, info):
        provider = info.data.get('provider', 'openai')
        valid = {'openai': ['onyx', 'echo'], 'elevenlabs': ['adam', 'josh', 'antoni', 'custom'], 'piper': ['local']}
        if value not in valid[provider]:
            raise ValueError('Hlas nepatří vybranému poskytovateli.')
        return value


FONTS = {
    'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'condensed': '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
    'serif': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
}


def voice_available(config, language, health):
    if config.provider == 'openai':
        return health['ai_scripts']
    if config.provider == 'elevenlabs':
        return health['elevenlabs']
    return health['voices'].get(language, False)
