from dataclasses import dataclass, field
from enum import Flag, auto
from types import ClassMethodDescriptorType, FunctionType
from typing import Optional

from utils.utils import read_temporary_setting, set_temporary_setting


class CodecEnum(Flag):
    FLAC = auto()  # Lossless, free
    ALAC = auto()  # Lossless, free, useless
    MQA = auto()  # Lossy, proprietary, terrible
    OPUS = auto()  # Lossy, free
    VORBIS = auto()  # Lossy, free
    MP3 = auto()  # Lossy, not fully free
    AAC = auto()  # Lossy, requires license
    HEAAC = auto()  # Lossy, requires license
    MHA1 = auto()  # Lossy, requires license, spatial
    EAC3 = auto()  # Specifically E-AC-3 JOC # Lossy, proprietary, spatial
    AC4 = auto()  # Specifically AC-4 IMS # Lossy, proprietary, spatial

class ContainerEnum(Flag):
    flac = auto()
    opus = auto()
    ogg = auto()
    m4a = auto()
    mp3 = auto()

@dataclass
class SearchResult:
    result_id: str
    name: Optional[str] = None
    artists: Optional[list] = None
    year: Optional[str] = None
    explicit: Optional[bool] = False
    additional: Optional[list] = None

@dataclass
class CodecData:
    pretty_name: str
    container: ContainerEnum
    lossless: bool
    spatial: bool
    proprietary: bool

codec_data = {
    CodecEnum.FLAC:   CodecData(pretty_name='FLAC',       container=ContainerEnum.flac, lossless=True,  spatial=False, proprietary=False),
    CodecEnum.ALAC:   CodecData(pretty_name='ALAC',       container=ContainerEnum.m4a,  lossless=True,  spatial=False, proprietary=False),
    CodecEnum.MQA:    CodecData(pretty_name='MQA',        container=ContainerEnum.flac, lossless=False, spatial=False, proprietary=True),
    CodecEnum.OPUS:   CodecData(pretty_name='Opus',       container=ContainerEnum.opus, lossless=False, spatial=False, proprietary=False),
    CodecEnum.VORBIS: CodecData(pretty_name='Vorbis',     container=ContainerEnum.ogg,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.MP3:    CodecData(pretty_name='MP3',        container=ContainerEnum.mp3,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.AAC:    CodecData(pretty_name='AAC-LC',     container=ContainerEnum.m4a,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.HEAAC:  CodecData(pretty_name='HE-AAC',     container=ContainerEnum.m4a,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.MHA1:   CodecData(pretty_name='MPEG-H 3D',  container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=False),
    CodecEnum.EAC3:   CodecData(pretty_name='E-AC-3 JOC', container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=True),
    CodecEnum.AC4:    CodecData(pretty_name='AC-4 IMS',   container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=True)
} # Note: spatial has priority over proprietary when deciding if a codec is enabled

class DownloadEnum(Flag):
    URL = auto()
    TEMP_FILE_PATH = auto() # Specifically designed for use with protected streams

class TemporarySettingsController:
    def __init__(self, module: str, settings_location: str):
        self.module = module
        self.settings_location = settings_location

    def read(self, setting: str, setting_type='custom'):
        if setting_type == 'custom':
            return read_temporary_setting(self.settings_location, self.module, 'custom_data', setting)
        elif setting_type == 'global':
            return read_temporary_setting(self.settings_location, self.module, 'custom_data', setting, global_mode=True)
        elif setting_type == 'jwt' and (setting == 'bearer' or setting == 'refresh'):
            return read_temporary_setting(self.settings_location, self.module, setting, None)
        else:
            raise Exception('Invalid temporary setting requested')

    def set(self, setting: str, value: str or object, setting_type='custom'):
        if setting_type == 'custom':
            set_temporary_setting(self.settings_location, self.module, 'custom_data', setting, value)
        elif setting_type == 'global':
            set_temporary_setting(self.settings_location, self.module, 'custom_data', setting, value, global_mode=True)
        elif setting_type == 'jwt' and (setting == 'bearer' or setting == 'refresh'):
            set_temporary_setting(self.settings_location, self.module, setting, None, value)
        else:
            raise Exception('Invalid temporary setting requested')

class ModuleFlags(Flag):
    startup_load = auto()
    standard_login = auto()
    hidden = auto()
    jwt_system_enable = auto()
    custom_url_parsing = auto()
    private = auto()

class ModuleModes(Flag):
    download = auto()
    playlist = auto()
    lyrics = auto()
    credits = auto()
    covers = auto()

@dataclass
class ModuleInformation:
    service_name: str
    module_supported_modes: ModuleModes
    global_settings: Optional[dict] = field(default_factory=dict)
    session_settings: Optional[dict] = field(default_factory=dict)
    flags: Optional[ModuleFlags] = field(default_factory=dict)
    netlocation_constant: Optional[str] = ''
    temporary_settings: Optional[list] = None
    url_constants: Optional[dict] = None
    test_url: Optional[str] = None

@dataclass
class ExtensionInformation:
    extension_type: str
    settings: dict

@dataclass
class DownloadTypeEnum(Flag):
    track = auto()
    playlist = auto()
    artist = auto()
    album = auto()

@dataclass # Kinda pointless, but still
class MediaIdentification:
    media_type: DownloadTypeEnum
    media_id: str
    service_name: str
    url: Optional[str] = None

class QualityEnum(Flag):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    LOSSLESS = auto()
    HIFI = auto()

@dataclass
class CodecOptions:
    proprietary_codecs: bool
    spatial_codecs: bool

class ImageFileTypeEnum(Flag):
    jpg = auto()
    png = auto()

class CoverCompressionEnum(Flag):
    low = auto()
    high = auto()

@dataclass
class CoverOptions:
    file_type: ImageFileTypeEnum
    resolution: int
    compression: CoverCompressionEnum

@dataclass
class OrpheusOptions:
    debug_mode: bool
    disable_subscription_check: bool
    quality_tier: QualityEnum # Here because of subscription checking
    album_search_return_only_albums: bool
    album_cache_optimisations: bool
    codec_options: CodecOptions
    default_cover_options: CoverOptions

@dataclass
class ModuleController:
    module_settings: dict
    extensions: dict
    temporary_settings_controller: TemporarySettingsController
    orpheus_options: OrpheusOptions
    get_current_timestamp: FunctionType
    module_error: ClassMethodDescriptorType

# TODO: add all artists here, not just the main one
@dataclass
class Tags:
    title: str
    album: str
    artist: str
    date: int
    explicit: Optional[bool] = None
    album_artist: Optional[str] = None
    track_number: Optional[str] = None
    total_tracks: Optional[str] = None
    copyright: Optional[str] = None
    isrc: Optional[str] = None
    upc: Optional[str] = None
    disc_number: Optional[str] = None
    total_discs: Optional[str] = None
    replay_gain: Optional[float] = None
    replay_peak: Optional[float] = None
    genre: Optional[list] = None
    lyrics: Optional[list] = None
    credits: Optional[list] = None

@dataclass
class CoverInfo:
    url: str
    file_type: ImageFileTypeEnum

@dataclass
class LyricsInfo:
    embedded: Optional[str] = None
    synced: Optional[str] = None

# TODO: get rid of CreditsInfo!
@dataclass
class CreditsInfo:
    type: str
    names: list

@dataclass
class AlbumInfo:
    album_name: str
    artist_name: str
    artist_id: str
    tracks: list
    album_year: Optional[str] = None
    explicit: Optional[bool] = None
    booklet_url: Optional[str] = None
    cover_url: Optional[str] = None
    cover_type: Optional[ImageFileTypeEnum] = ImageFileTypeEnum.jpg

@dataclass
class ArtistInfo:
    artist_name: str
    albums: list

@dataclass
class PlaylistInfo:
    playlist_name: str
    playlist_creator_name: str
    tracks: list
    playlist_year: Optional[str] = None
    explicit: Optional[bool] = None
    playlist_creator_id: Optional[str] = None
    cover_url: Optional[str] = None
    cover_type: Optional[ImageFileTypeEnum] = ImageFileTypeEnum.jpg

@dataclass
class TrackInfo:
    track_name: str
    album_id: str
    album_name: str
    artist_name: str
    artist_id: str
    download_type: DownloadEnum
    tags: Tags
    codec: CodecEnum
    cover_url: str
    bit_depth: Optional[int] = 16
    sample_rate: Optional[float] = 44.1
    bitrate: Optional[str] = None
    file_url: Optional[str] = None
    file_url_headers: Optional[dict] = None
    error: Optional[str] = None
