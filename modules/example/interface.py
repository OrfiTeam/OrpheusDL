from utils.models import *
from utils.utils import create_temp_filename


module_information = ModuleInformation( # Only service_name and module_supported_modes are mandatory
    service_name = 'Example',
    module_supported_modes = ModuleModes.download | ModuleModes.lyrics | ModuleModes.covers | ModuleModes.credits,
    flags = ModuleFlags.hidden,
    # Flags:
        # startup_load: load module on startup
        # hidden: hides module from CLI help options
        # jwt_system_enable: handles bearer and refresh tokens automatically, though currently untested
        # private: override any public modules, only enabled with the -p/--private argument, currently broken
    global_settings = {},
    global_storage_variables = [],
    session_settings = {},
    session_storage_variables = ['access_token'],
    netlocation_constant = 'example', 
    test_url = 'https://player.example.com/track/idhere',
    url_constants = { # This is the default if no url_constants is given. Unused if custom_url_parsing is flagged
        'track': DownloadTypeEnum.track,
        'album': DownloadTypeEnum.album,
        'playlist': DownloadTypeEnum.playlist,
        'artist': DownloadTypeEnum.artist
    }, # How this works: if '/track/' is detected in the URL, then track downloading is triggered
    login_behaviour = ManualEnum.manual, # setting to ManualEnum.manual disables Orpheus automatically calling login() when needed
    url_decoding = ManualEnum.orpheus # setting to ManualEnum.manual disables Orpheus' automatic url decoding which works as follows:
    # taking the url_constants dict as a list of constants to check for in the url's segments, and the final part of the URL as the ID
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        settings = module_controller.module_settings
        self.session = (settings['app_id'], settings['app_secret']) # API class goes here
        self.session.auth_token = module_controller.temporary_settings_controller.read('access_token')
        self.module_controller = module_controller

        self.quality_parse = {
            QualityEnum.MINIMUM: 0,
            QualityEnum.LOW: 1,
            QualityEnum.MEDIUM: 2,
            QualityEnum.HIGH: 3,
            QualityEnum.LOSSLESS: 4,
            QualityEnum.HIFI: 5
        }
        if not module_controller.orpheus_options.disable_subscription_check and (self.quality_parse[module_controller.orpheus_options.quality_tier] > self.session.get_user_tier()):
            print('Example: quality set in the settings is not accessible by the current subscription')

    def login(self, email: str, password: str): # Called automatically by Orpheus when standard_login is flagged, otherwise optional
        token = self.session.login(email, password)
        self.session.auth_token = token
        self.module_controller.temporary_settings_controller.set('token', token)

    def get_track_info(self, track_id: str, quality_tier: QualityEnum, codec_options: CodecOptions, data={}) -> TrackInfo: # Mandatory
        quality_tier = self.quality_parse[quality_tier]
        track_data = data[track_id] if data and track_id in data else self.session.get_track(track_id)

        tags = Tags( # every single one of these is optional
            album_artist = '',
            composer = '',
            track_number = 1,
            total_tracks = 1,
            copyright = '',
            isrc = '',
            upc = '',
            disc_number = 1, # None/0/1 if no discs
            total_discs = 1, # None/0/1 if no discs
            replay_gain = 0.0,
            replay_peak = 0.0,
            genres = [],
            release_date = '1969-09-06' # Format: YYYY-MM-DD
        )

        return TrackInfo(
            name = '',
            album_id = '',
            album = '',
            artists = [''],
            tags = tags,
            codec = CodecEnum.FLAC,
            cover_url = '', # make sure to check module_controller.orpheus_options.default_cover_options
            release_year = 2021,
            explicit = False,
            artist_id = '', # optional
            animated_cover_url = '', # optional
            description = '', # optional
            bit_depth = 16, # optional
            sample_rate = 44.1, # optional
            bitrate = 1411, # optional
            download_extra_kwargs = {'file_url': '', 'codec': ''}, # optional only if download_type isn't DownloadEnum.TEMP_FILE_PATH, whatever you want
            cover_extra_kwargs = {'data': {track_id: ''}}, # optional, whatever you want, but be very careful
            credits_extra_kwargs = {'data': {track_id: ''}}, # optional, whatever you want, but be very careful
            lyrics_extra_kwargs = {'data': {track_id: ''}}, # optional, whatever you want, but be very careful
            error = '' # only use if there is an error
        )

    def get_track_download(self, file_url, codec):
        track_location = create_temp_filename()
        # Do magic here
        return TrackDownloadInfo(
            download_type = DownloadEnum.URL,
            file_url = '', # optional only if download_type isn't DownloadEnum.URL
            file_url_headers = {}, # optional
            temp_file_path = track_location
        )

    def get_album_info(self, album_id: str, data={}) -> Optional[AlbumInfo]: # Mandatory if ModuleModes.download
        album_data = data[album_id] if album_id in data else self.session.get_album(album_id)

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
            animated_cover_url = '', # optional
            description = '', # optional
            track_extra_kwargs = {'data': ''} # optional, whatever you want
        )

    def get_playlist_info(self, playlist_id: str, data={}) -> PlaylistInfo:  # Mandatory if either ModuleModes.download or ModuleModes.playlist
        playlist_data = data[playlist_id] if playlist_id in data else self.session.get_playlist(playlist_id)

        return PlaylistInfo(
            name = '',
            creator = '',
            tracks = [],
            release_year = '',
            explicit = False,
            creator_id = '', # optional
            cover_url = '', # optional
            cover_type = ImageFileTypeEnum.jpg, # optional
            animated_cover_url = '', # optional
            description = '', # optional
            track_extra_kwargs = {'data': ''} # optional, whatever you want
        )

    def get_artist_info(self, artist_id: str, get_credited_albums: bool) -> ArtistInfo: # Mandatory if ModuleModes.download
        # get_credited_albums means stuff like remix compilations the artist was part of
        artist_data = self.session.get_artist(artist_id)

        return ArtistInfo(
            name = '',
            albums = [], # optional
            album_extra_kwargs = {'data': ''}, # optional, whatever you want
            tracks = [], # optional
            track_extra_kwargs = {'data': ''} # optional, whatever you want
        )

    def get_track_credits(self, track_id: str, data={}): # Mandatory if ModuleModes.credits
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)
        credits = track_data['credits']
        credits_dict = {}
        return [CreditsInfo(k, v) for k, v in credits_dict.items()]
    
    def get_track_cover(self, track_id: str, cover_options: CoverOptions, data={}) -> CoverInfo: # Mandatory if ModuleModes.covers
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)
        cover_info = track_data['cover']
        return CoverInfo(url='', file_type=ImageFileTypeEnum.jpg)

    def get_track_lyrics(self, track_id: str, data={}) -> LyricsInfo: # Mandatory if ModuleModes.lyrics
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)
        lyrics = track_data['lyrics']
        return LyricsInfo(embedded='', synced='') # both optional if not found

    def search(self, query_type: DownloadTypeEnum, query: str, track_info: TrackInfo = None, limit: int = 10): # Mandatory
        results = {}
        if track_info and track_info.tags.isrc:
            results = self.session.search(query_type.name, track_info.tags.isrc, limit)
        if not results:
            results = self.session.search(query_type.name, query, limit)

        return [SearchResult(
                result_id = '',
                name = '', # optional only if a lyrics/covers only module
                artists = [], # optional only if a lyrics/covers only module or an artist search
                year = '', # optional
                explicit = False, # optional
                additional = [], # optional, used to convey more info when using orpheus.py search (not luckysearch, for obvious reasons)
                extra_kwargs = {'data': {i['id']: i}} # optional, whatever you want. NOTE: BE CAREFUL! this can be given to:
                # get_track_info, get_album_info, get_artist_info with normal search results, and
                # get_track_credits, get_track_cover, get_track_lyrics in the case of other modules using this module just for those.
                # therefore, it's recommended to choose something generic like 'data' rather than specifics like 'cover_info'
                # or, you could use both, keeping a data field just in case track data is given, while keeping the specifics, but that's overcomplicated
            ) for i in results]
