from utils.models import *


module_information = ModuleInformation( # Only service_name and module_supported_modes are mandatory
    service_name = 'Example',
    module_supported_modes = ModuleModes.download | ModuleModes.lyrics | ModuleModes.covers | ModuleModes.credits,
    flags = ModuleFlags.hidden,
    # Flags:
        # startup_load: load module on startup
        # standard_login: handles logins for the module automatically, calling login() when needed
        # hidden: hides module from CLI help options
        # jwt_system_enable: handles bearer and refresh tokens automatically, though currently untested
        # custom_url_parsing: instead of the simple system of taking the url_constants dict as input, 
        #     and the final part of the URL as the ID, let the module handle it instead
        # private: override any public modules, only enabled with the -p/--private argument, currently broken
    global_settings = {},
    session_settings = {},
    temporary_settings = ['access_token'],
    netlocation_constant = 'example', 
    test_url = 'https://player.example.com/track/idhere',
    url_constants = { # This is the default if no url_constants is given. Unused if custom_url_parsing is flagged
        'track': DownloadTypeEnum.track,
        'album': DownloadTypeEnum.album,
        'playlist': DownloadTypeEnum.playlist,
        'artist': DownloadTypeEnum.artist
    } # How this works: if '/track/' is detected in the URL, then track downloading is triggered
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        settings = module_controller.module_settings
        self.session = (settings['app_id'], settings['app_secret']) # API class goes here
        self.session.auth_token = module_controller.temporary_settings_controller.read('access_token')
        self.module_controller = module_controller

        self.track_cache = {}

    def login(self, email: str, password: str): # Called automatically by Orpheus when standard_login is flagged, otherwise optional
        token = self.session.login(email, password)
        self.session.auth_token = token
        self.module_controller.temporary_settings_controller.set('token', token)

    def get_track_info(self, track_id: str, quality_tier: QualityEnum, codec_options: CodecOptions) -> TrackInfo: # Mandatory
        quality_parse = {
            QualityEnum.LOW: 1,
            QualityEnum.MEDIUM: 2,
            QualityEnum.HIGH: 3,
            QualityEnum.LOSSLESS: 4,
            QualityEnum.HIFI: 5
        }
        quality_tier = quality_parse[quality_tier]
        track_data = self.track_cache[track_id] if track_id in self.track_cache else self.session.get_track(track_id, quality_tier)

        tags = Tags( # every single one of these is optional
            album_artist = '',
            track_number = 1,
            total_tracks = 1,
            copyright = '',
            isrc = '',
            upc = 111111111111,
            disc_number = 1, # None/0/1 if no discs
            total_discs = 1, # None/0/1 if no discs
            replay_gain = 0.0,
            replay_peak = 0.0,
            genres = []
        )

        return TrackInfo(
            name = '',
            album_id = '',
            album_name = '',
            artists = [''],
            download_type = DownloadEnum.URL,
            tags = tags,
            codec = CodecEnum.FLAC,
            cover_url = '', # make sure to check module_controller.orpheus_options.default_cover_options
            release_year = 2021,
            explicit = False,
            artist_id = '', # optional
            animated_cover_url = '', # optional
            bit_depth = 16, # optional
            sample_rate = 44.1, # optional
            bitrate = 1411, # optional
            file_url = '', # optional only if download_type isn't DownloadEnum.URL
            file_url_headers = {}, # optional
            error = '' # only use if there is an error
        )

    def get_album_info(self, album_id: str, get_only_albums: bool) -> Optional[AlbumInfo]: # Mandatory if ModuleModes.download
        # get_only_albums means no singles and stuff I think, not sure what Dniel97 meant by that
        album_data = self.session.get_album(album_id) # Make sure to cache tracks into track_cache if possible

        return AlbumInfo(
            name = '',
            artist = '',
            tracks = [],
            release_year = '',
            explicit = False,
            artist_id = '', # optional
            booklet_url = '', # optional
            cover_url = '', # optional
            cover_type = ImageFileTypeEnum.jpg, # optional
            all_track_cover_jpg_url = '', # technically optional, but HIGHLY recommended
            animated_cover_url = '' # optional
        )

    def get_playlist_info(self, playlist_id: str) -> PlaylistInfo:  # Mandatory if either ModuleModes.download or ModuleModes.playlist
        playlist_data = self.session.get_playlist(playlist_id) # Make sure to cache tracks into track_cache if possible

        return PlaylistInfo(
            name = '',
            creator = '',
            tracks = [],
            release_year = '',
            explicit = False,
            creator_id = '', # optional
            cover_url = '', # optional
            cover_type = ImageFileTypeEnum.jpg, # optional
            animated_cover_url = '' # optional
        )

    def get_artist_info(self, artist_id: str, get_credited_albums: bool) -> ArtistInfo: # Mandatory if ModuleModes.download
        # get_credited_albums means stuff like remix compilations the artist was part of
        artist_data = self.session.get_artist(artist_id)

        return ArtistInfo(
            name = '',
            albums = []
        )

    def get_track_credits(self, track_id: str): # Mandatory if ModuleModes.credits
        track_data = self.track_cache[track_id] if track_id in self.track_cache else self.session.get_track(track_id, quality_tier=1)
        track_contributors = track_data['credits'] 
        credits_dict = {}
        return [CreditsInfo(k, v) for k, v in credits_dict.items()]
    
    def get_track_cover(self, track_id: str, cover_options: CoverOptions) -> CoverInfo: # Mandatory if ModuleModes.covers
        track_data = self.track_cache[track_id] if track_id in self.track_cache else self.session.get_track(track_id, quality_tier=1)
        track_cover = track_data['cover_url'] 
        return CoverInfo(url='', file_type=ImageFileTypeEnum.jpg)
    
    def get_track_lyrics(self, track_id: str) -> LyricsInfo: # Mandatory if ModuleModes.lyrics
        track_data = self.track_cache[track_id] if track_id in self.track_cache else self.session.get_track(track_id, quality_tier=1)
        track_cover = track_data['lyrics'] 
        return LyricsInfo(embedded='', synced='') # Both optional if not found

    def search(self, query_type: DownloadTypeEnum, query: str, tags: Tags = None, limit: int = 10): # Mandatory
        results = {} # Make sure to cache tracks into track_cache if possible
        if tags and tags.isrc:
            results = self.session.search(query_type.name, tags.isrc, limit)
        if not results:
            results = self.session.search(query_type.name, query, limit)

        return [SearchResult(
            result_id = '',
            name = '', # optional, only if a lyrics/covers only module
            artists = [], # optional, only if a lyrics/covers only module or an artist search
            year = '', # optional
            explicit = False, # optional
            additional = [], # optional, used to convey more info when using orpheus.py search (not luckysearch, for obvious reasons)
            ) for i in results]