import os
from dataclasses import dataclass, field
from enum import Flag, auto
from types import ClassMethodDescriptorType, FunctionType
from typing import Optional

from utils.utils import read_temporary_setting, set_temporary_setting


class Oprinter:  # Could change to inherit from print class instead, but this is fine
    def __init__(self):
        self.indent_number = 1
        self.printing_enabled = True
        self.multiplier = 8

    def set_indent_number(self, number: int):
        try:
            size = os.get_terminal_size().columns
            if 60 < size < 80:
                self.multiplier = int((size - 60)/2.5)
            elif size < 60:
                self.multiplier = 0
            else:
                self.multiplier = 8
        except:
            self.multiplier = 8

        self.indent_number = number * self.multiplier

    def oprint(self, inp: str, drop_level: int = 0):
        if self.printing_enabled:
            print(' ' * (self.indent_number - drop_level * self.multiplier) + inp)


class CodecEnum(Flag):
    FLAC = auto()  # Lossless, free
    ALAC = auto()  # Lossless, free, useless
    WAV = auto()  # Lossless (uncompressed), free, useless
    MQA = auto()  # Lossy, proprietary, terrible
    OPUS = auto()  # Lossy, free
    VORBIS = auto()  # Lossy, free
    MP3 = auto()  # Lossy, not fully free
    AAC = auto()  # Lossy, requires license
    HEAAC = auto()  # Lossy, requires license
    MHA1 = auto()  # Lossy, requires license, spatial
    EAC3 = auto()  # Specifically E-AC-3 JOC # Lossy, proprietary, spatial
    AC4 = auto()  # Specifically AC-4 IMS # Lossy, proprietary, spatial
    AC3 = auto()  # Lossy, proprietary, spatial kinda
    NONE = auto()  # No codec


class ContainerEnum(Flag):
    flac = auto()
    wav = auto()
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
    duration: Optional[int] = None  # Duration in whole seconds
    additional: Optional[list] = None
    extra_kwargs: Optional[dict] = field(default_factory=dict)


@dataclass
class CodecData:
    pretty_name: str
    container: ContainerEnum
    lossless: bool
    spatial: bool
    proprietary: bool


codec_data = {
    CodecEnum.FLAC:   CodecData(pretty_name='FLAC',          container=ContainerEnum.flac, lossless=True,  spatial=False, proprietary=False),
    CodecEnum.ALAC:   CodecData(pretty_name='ALAC',          container=ContainerEnum.m4a,  lossless=True,  spatial=False, proprietary=False),
    CodecEnum.WAV:    CodecData(pretty_name='WAVE',          container=ContainerEnum.wav,  lossless=True,  spatial=False, proprietary=False),
    CodecEnum.MQA:    CodecData(pretty_name='MQA',           container=ContainerEnum.flac, lossless=False, spatial=False, proprietary=True),
    CodecEnum.OPUS:   CodecData(pretty_name='Opus',          container=ContainerEnum.opus, lossless=False, spatial=False, proprietary=False),
    CodecEnum.VORBIS: CodecData(pretty_name='Vorbis',        container=ContainerEnum.ogg,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.MP3:    CodecData(pretty_name='MP3',           container=ContainerEnum.mp3,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.AAC:    CodecData(pretty_name='AAC-LC',        container=ContainerEnum.m4a,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.HEAAC:  CodecData(pretty_name='HE-AAC',        container=ContainerEnum.m4a,  lossless=False, spatial=False, proprietary=False),
    CodecEnum.MHA1:   CodecData(pretty_name='MPEG-H 3D',     container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=False),
    CodecEnum.EAC3:   CodecData(pretty_name='E-AC-3 JOC',    container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=True),
    CodecEnum.AC4:    CodecData(pretty_name='AC-4 IMS',      container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=True),
    CodecEnum.AC3:    CodecData(pretty_name='Dolby Digital', container=ContainerEnum.m4a,  lossless=False, spatial=True,  proprietary=True),
    CodecEnum.NONE:   CodecData(pretty_name='Error',         container=ContainerEnum.m4a,  lossless=False, spatial=False, proprietary=False)
}  # Note: spatial has priority over proprietary when deciding if a codec is enabled


class DownloadEnum(Flag):
    URL = auto()
    TEMP_FILE_PATH = auto()  # Specifically designed for use with protected streams
    MPD = auto()


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
    hidden = auto()
    enable_jwt_system = auto()
    private = auto()
    uses_data = auto()
    needs_cover_resize = auto()


class ModuleModes(Flag):
    download = auto()
    playlist = auto()
    lyrics = auto()
    credits = auto()
    covers = auto()


class ManualEnum(Flag):
    orpheus = auto()
    manual = auto()


@dataclass
class ModuleInformation:
    service_name: str
    module_supported_modes: ModuleModes
    global_settings: Optional[dict] = field(default_factory=dict)
    global_storage_variables: Optional[list] = None
    session_settings: Optional[dict] = field(default_factory=dict)
    session_storage_variables: Optional[list] = None
    flags: Optional[ModuleFlags] = field(default_factory=dict)
    netlocation_constant: Optional[str] or Optional[list] = field(default_factory=list) # not sure if this works with python 3.7/3.8
    # note that by setting netlocation_constant to setting.X, it will use that setting instead
    url_constants: Optional[dict] = None
    test_url: Optional[str] = None
    url_decoding: Optional[ManualEnum] = ManualEnum.orpheus
    login_behaviour: Optional[ManualEnum] = ManualEnum.orpheus


@dataclass
class ExtensionInformation:
    extension_type: str
    settings: dict


class DownloadTypeEnum(Flag):
    track = auto()
    playlist = auto()
    artist = auto()
    album = auto()


@dataclass
class MediaIdentification:
    media_type: DownloadTypeEnum
    media_id: str
    extra_kwargs: Optional[dict] = field(default_factory=dict)


class QualityEnum(Flag):
    MINIMUM = auto()
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
    webp = auto()


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
    quality_tier: QualityEnum  # Here because of subscription checking
    default_cover_options: CoverOptions


@dataclass
class ModuleController:
    module_settings: dict
    data_folder: str
    extensions: dict
    temporary_settings_controller: TemporarySettingsController
    orpheus_options: OrpheusOptions
    get_current_timestamp: FunctionType
    printer_controller: Oprinter
    module_error: ClassMethodDescriptorType  # Will eventually be deprecated *sigh*


@dataclass
class Tags:
    album_artist: Optional[str] = None
    composer: Optional[str] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    copyright: Optional[str] = None
    isrc: Optional[str] = None
    upc: Optional[str] = None
    disc_number: Optional[int] = None
    total_discs: Optional[int] = None
    replay_gain: Optional[float] = None
    replay_peak: Optional[float] = None
    genres: Optional[list] = None
    release_date: Optional[str] = None  # Format: YYYY-MM-DD
    description: Optional[str] = None
    comment: Optional[str] = None
    label: Optional[str] = None
    extra_tags: Optional[dict] = field(default_factory=dict)


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
    name: str
    artist: str
    tracks: list
    release_year: int
    duration: Optional[int] = None  # Duration in whole seconds
    explicit: Optional[bool] = False
    artist_id: Optional[str] = None
    quality: Optional[str] = None
    booklet_url: Optional[str] = None
    cover_url: Optional[str] = None
    upc: Optional[str] = None
    cover_type: Optional[ImageFileTypeEnum] = ImageFileTypeEnum.jpg
    all_track_cover_jpg_url: Optional[str] = None
    animated_cover_url: Optional[str] = None
    description: Optional[str] = None
    track_extra_kwargs: Optional[dict] = field(default_factory=dict)


@dataclass
class ArtistInfo:
    name: str
    albums: Optional[list] = field(default_factory=list)
    album_extra_kwargs: Optional[dict] = field(default_factory=dict)
    tracks: Optional[list] = field(default_factory=list)
    track_extra_kwargs: Optional[dict] = field(default_factory=dict)


@dataclass
class PlaylistInfo:
    name: str
    creator: str
    tracks: list
    release_year: int
    duration: Optional[int] = None  # Duration in whole seconds
    explicit: Optional[bool] = False
    creator_id: Optional[str] = None
    cover_url: Optional[str] = None
    cover_type: Optional[ImageFileTypeEnum] = ImageFileTypeEnum.jpg
    animated_cover_url: Optional[str] = None
    description: Optional[str] = None
    track_extra_kwargs: Optional[dict] = field(default_factory=dict)


@dataclass
class TrackInfo:
    name: str
    album: str
    album_id: str
    artists: list
    tags: Tags
    codec: CodecEnum
    cover_url: str
    release_year: int
    duration: Optional[int] = None  # Duration in whole seconds
    explicit: Optional[bool] = None
    artist_id: Optional[str] = None
    animated_cover_url: Optional[str] = None
    description: Optional[str] = None
    bit_depth: Optional[int] = 16
    sample_rate: Optional[float] = 44.1
    bitrate: Optional[int] = None
    download_extra_kwargs: Optional[dict] = field(default_factory=dict)
    cover_extra_kwargs: Optional[dict] = field(default_factory=dict)
    credits_extra_kwargs: Optional[dict] = field(default_factory=dict)
    lyrics_extra_kwargs: Optional[dict] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TrackDownloadInfo:
    download_type: DownloadEnum
    file_url: Optional[str] = None
    file_url_headers: Optional[dict] = None
    temp_file_path: Optional[str] = None
    different_codec: Optional[CodecEnum] = None
