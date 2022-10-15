import logging, os, ffmpeg, sys
import shutil
from dataclasses import asdict
from time import strftime, gmtime

from ffmpeg import Error

from orpheus.tagging import tag_file
from utils.models import *
from utils.utils import *
from utils.exceptions import *


def beauty_format_seconds(seconds: int) -> str:
    time_data = gmtime(seconds)

    time_format = "%Mm:%Ss"
    # if seconds are higher than 3600s also add the hour format
    if time_data.tm_hour > 0:
        time_format = "%Hh:" + time_format
    # TODO: also add days to time_format if hours > 24?

    # return the formatted time string
    return strftime(time_format, time_data)


class Downloader:
    def __init__(self, settings, module_controls, oprinter, path):
        self.path = path if path.endswith('/') else path + '/' 
        self.third_party_modules = None
        self.download_mode = None
        self.service = None
        self.service_name = None
        self.module_list = module_controls['module_list']
        self.module_settings = module_controls['module_settings']
        self.loaded_modules = module_controls['loaded_modules']
        self.load_module = module_controls['module_loader']
        self.global_settings = settings

        self.oprinter = oprinter
        self.print = self.oprinter.oprint
        self.set_indent_number = self.oprinter.set_indent_number

    def search_by_tags(self, module_name, track_info: TrackInfo):
        return self.loaded_modules[module_name].search(DownloadTypeEnum.track, f'{track_info.name} {" ".join(track_info.artists)}', track_info=track_info)

    def _add_track_m3u_playlist(self, m3u_playlist: str, track_info: TrackInfo, track_location: str):
        if self.global_settings['playlist']['extended_m3u']:
            with open(m3u_playlist, 'a', encoding='utf-8') as f:
                # if no duration exists default to -1
                duration = track_info.duration if track_info.duration else -1
                # write the extended track header
                f.write(f'#EXTINF:{duration}, {track_info.artists[0]} - {track_info.name}\n')

        with open(m3u_playlist, 'a', encoding='utf-8') as f:
            if self.global_settings['playlist']['paths_m3u'] == "absolute":
                # add the absolute paths to the playlist
                f.write(f'{os.path.abspath(track_location)}\n')
            else:
                # add the relative paths to the playlist by subtracting the track_location with the m3u_path
                f.write(f'{os.path.relpath(track_location, os.path.dirname(m3u_playlist))}\n')

            # add an extra new line to the extended format
            f.write('\n') if self.global_settings['playlist']['extended_m3u'] else None

    def download_playlist(self, playlist_id, custom_module=None, extra_kwargs={}):
        self.set_indent_number(1)

        playlist_info: PlaylistInfo = self.service.get_playlist_info(playlist_id, **extra_kwargs)
        self.print(f'=== Downloading playlist {playlist_info.name} ({playlist_id}) ===', drop_level=1)
        self.print(f'Playlist creator: {playlist_info.creator}' + (f' ({playlist_info.creator_id})' if playlist_info.creator_id else ''))
        if playlist_info.release_year: self.print(f'Playlist creation year: {playlist_info.release_year}')
        if playlist_info.duration: self.print(f'Duration: {beauty_format_seconds(playlist_info.duration)}')
        number_of_tracks = len(playlist_info.tracks)
        self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')
        
        playlist_tags = {k: sanitise_name(v) for k, v in asdict(playlist_info).items()}
        playlist_tags['explicit'] = ' [E]' if playlist_info.explicit else ''
        playlist_path = self.path + self.global_settings['formatting']['playlist_format'].format(**playlist_tags)
        # fix path character limit
        playlist_path = fix_file_limit(playlist_path) + '/'
        os.makedirs(playlist_path, exist_ok=True)
        
        if playlist_info.cover_url:
            self.print('Downloading playlist cover')
            download_file(playlist_info.cover_url, f'{playlist_path}Cover.{playlist_info.cover_type.name}', artwork_settings=self._get_artwork_settings())
        
        if playlist_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated playlist cover')
            download_file(playlist_info.animated_cover_url, playlist_path + 'Cover.mp4', enable_progress_bar=True)
        
        if playlist_info.description:
            with open(playlist_path + 'Description.txt', 'w', encoding='utf-8') as f: f.write(playlist_info.description)

        m3u_playlist_path = None
        if self.global_settings['playlist']['save_m3u']:
            if self.global_settings['playlist']['paths_m3u'] not in {"absolute", "relative"}:
                raise ValueError(f'Invalid value for paths_m3u: "{self.global_settings["playlist"]["paths_m3u"]}",'
                                 f' must be either "absolute" or "relative"')

            m3u_playlist_path = playlist_path + f'{playlist_tags["name"]}.m3u'

            # create empty file
            with open(m3u_playlist_path, 'w', encoding='utf-8') as f:
                f.write('')

            # if extended format add the header
            if self.global_settings['playlist']['extended_m3u']:
                with open(m3u_playlist_path, 'a', encoding='utf-8') as f:
                    f.write('#EXTM3U\n\n')

        tracks_errored = set()
        if custom_module:
            supported_modes = self.module_settings[custom_module].module_supported_modes 
            if ModuleModes.download not in supported_modes and ModuleModes.playlist not in supported_modes:
                raise Exception(f'Module "{custom_module}" cannot be used to download a playlist') # TODO: replace with ModuleDoesNotSupportAbility
            self.print(f'Service used for downloading: {self.module_settings[custom_module].service_name}')
            original_service = str(self.service_name)
            self.load_module(custom_module)
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
                codec_options = CodecOptions(
                    spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                    proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
                )
                track_info: TrackInfo = self.loaded_modules[original_service].get_track_info(track_id, quality_tier, codec_options, **playlist_info.track_extra_kwargs)
                
                self.service = self.loaded_modules[custom_module]
                self.service_name = custom_module
                results = self.search_by_tags(custom_module, track_info)
                track_id_new = results[0].result_id if len(results) else None
                
                if track_id_new:
                    self.download_track(track_id_new, album_location=playlist_path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=results[0].extra_kwargs)
                else:
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    if ModuleModes.download in self.module_settings[original_service].module_supported_modes:
                        self.service = self.loaded_modules[original_service]
                        self.service_name = original_service
                        self.print(f'Track {track_info.name} not found, using the original service as a fallback', drop_level=1)
                        self.download_track(track_id, album_location=playlist_path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=playlist_info.track_extra_kwargs)
                    else:
                        self.print(f'Track {track_info.name} not found, skipping')
        else:
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                self.download_track(track_id, album_location=playlist_path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=playlist_info.track_extra_kwargs)

        self.set_indent_number(1)
        self.print(f'=== Playlist {playlist_info.name} downloaded ===', drop_level=1)

        if tracks_errored: logging.debug('Failed tracks: ' + ', '.join(tracks_errored))

    def _create_album_location(self, path: str, album_id: str, album_info: AlbumInfo) -> str:
        # Clean up album tags and add special explicit and additional formats
        album_tags = {k: sanitise_name(v) for k, v in asdict(album_info).items()}
        album_tags['id'] = str(album_id)
        album_tags['quality'] = f' [{album_info.quality}]' if album_info.quality else ''
        album_tags['explicit'] = ' [E]' if album_info.explicit else ''
        album_path = path + self.global_settings['formatting']['album_format'].format(**album_tags)
        # fix path character limit
        album_path = fix_file_limit(album_path) + '/'
        os.makedirs(album_path, exist_ok=True)

        return album_path

    def _download_album_files(self, album_path: str, album_info: AlbumInfo):
        if album_info.cover_url:
            self.print('Downloading album cover')
            download_file(album_info.cover_url, f'{album_path}Cover.{album_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

        if album_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated album cover')
            download_file(album_info.animated_cover_url, album_path + 'Cover.mp4', enable_progress_bar=True)

        if album_info.description:
            with open(album_path + 'Description.txt', 'w', encoding='utf-8') as f:
                f.write(album_info.description)  # Also add support for this with singles maybe?

    def download_album(self, album_id, artist_name='', path=None, indent_level=1, extra_kwargs={}):
        self.set_indent_number(indent_level)

        album_info: AlbumInfo = self.service.get_album_info(album_id, **extra_kwargs)
        if not album_info:
            return
        number_of_tracks = len(album_info.tracks)
        path = self.path if not path else path

        if number_of_tracks > 1 or self.global_settings['formatting']['force_album_format']:
            # Creates the album_location folders
            album_path = self._create_album_location(path, album_id, album_info)
        
            if self.download_mode is DownloadTypeEnum.album:
                self.set_indent_number(1)
            elif self.download_mode is DownloadTypeEnum.artist:
                self.set_indent_number(2)

            self.print(f'=== Downloading album {album_info.name} ({album_id}) ===', drop_level=1)
            self.print(f'Artist: {album_info.artist} ({album_info.artist_id})')
            if album_info.release_year: self.print(f'Year: {album_info.release_year}')
            if album_info.duration: self.print(f'Duration: {beauty_format_seconds(album_info.duration)}')
            self.print(f'Number of tracks: {number_of_tracks!s}')
            self.print(f'Service: {self.module_settings[self.service_name].service_name}')

            if album_info.booklet_url and not os.path.exists(album_path + 'Booklet.pdf'):
                self.print('Downloading booklet')
                download_file(album_info.booklet_url, album_path + 'Booklet.pdf')
            
            cover_temp_location = download_to_temp(album_info.all_track_cover_jpg_url) if album_info.all_track_cover_jpg_url else ''

            # Download booklet, animated album cover and album cover if present
            self._download_album_files(album_path, album_info)

            for index, track_id in enumerate(album_info.tracks, start=1):
                self.set_indent_number(indent_level + 1)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                self.download_track(track_id, album_location=album_path, track_index=index, number_of_tracks=number_of_tracks, main_artist=artist_name, cover_temp_location=cover_temp_location, indent_level=indent_level+1, extra_kwargs=album_info.track_extra_kwargs)

            self.set_indent_number(indent_level)
            self.print(f'=== Album {album_info.name} downloaded ===', drop_level=1)
            if cover_temp_location: silentremove(cover_temp_location)
        elif number_of_tracks == 1:
            self.download_track(album_info.tracks[0], album_location=path, number_of_tracks=1, main_artist=artist_name, indent_level=indent_level, extra_kwargs=album_info.track_extra_kwargs)

        return album_info.tracks

    def download_artist(self, artist_id, extra_kwargs={}):
        artist_info: ArtistInfo = self.service.get_artist_info(artist_id, self.global_settings['artist_downloading']['return_credited_albums'], **extra_kwargs)
        artist_name = artist_info.name

        self.set_indent_number(1)

        number_of_albums = len(artist_info.albums)
        number_of_tracks = len(artist_info.tracks)

        self.print(f'=== Downloading artist {artist_name} ({artist_id}) ===', drop_level=1)
        if number_of_albums: self.print(f'Number of albums: {number_of_albums!s}')
        if number_of_tracks: self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')
        artist_path = self.path + sanitise_name(artist_name) + '/'

        self.set_indent_number(2)
        tracks_downloaded = []
        for index, album_id in enumerate(artist_info.albums, start=1):
            print()
            self.print(f'Album {index}/{number_of_albums}', drop_level=1)
            tracks_downloaded += self.download_album(album_id, artist_name=artist_name, path=artist_path, indent_level=2, extra_kwargs=artist_info.album_extra_kwargs)

        self.set_indent_number(2)
        skip_tracks = self.global_settings['artist_downloading']['separate_tracks_skip_downloaded']
        tracks_to_download = [i for i in artist_info.tracks if (i not in tracks_downloaded and skip_tracks) or not skip_tracks]
        number_of_tracks_new = len(tracks_to_download)
        for index, track_id in enumerate(tracks_to_download, start=1):
            print()
            self.print(f'Track {index}/{number_of_tracks_new}', drop_level=1)
            self.download_track(track_id, album_location=artist_path, main_artist=artist_name, number_of_tracks=1, indent_level=2, extra_kwargs=artist_info.track_extra_kwargs)

        self.set_indent_number(1)
        tracks_skipped = number_of_tracks - number_of_tracks_new
        if tracks_skipped > 0: self.print(f'Tracks skipped: {tracks_skipped!s}', drop_level=1)
        self.print(f'=== Artist {artist_name} downloaded ===', drop_level=1)

    def download_track(self, track_id, album_location='', main_artist='', track_index=0, number_of_tracks=0, cover_temp_location='', indent_level=1, m3u_playlist=None, extra_kwargs={}):
        quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
        codec_options = CodecOptions(
            spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
            proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
        )
        track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, **extra_kwargs)
        
        if main_artist.lower() not in [i.lower() for i in track_info.artists] and self.global_settings['advanced']['ignore_different_artists'] and self.download_mode is DownloadTypeEnum.artist:
           self.print('Track is not from the correct artist, skipping', drop_level=1)
           return

        if not self.global_settings['formatting']['force_album_format']:
            if track_index:
                track_info.tags.track_number = track_index
            if number_of_tracks:
                track_info.tags.total_tracks = number_of_tracks
        zfill_number = len(str(track_info.tags.total_tracks)) if self.download_mode is not DownloadTypeEnum.track else 1
        zfill_lambda = lambda input : sanitise_name(str(input)).zfill(zfill_number) if input is not None else None

        # Separate copy of tags for formatting purposes
        zfill_enabled, zfill_list = self.global_settings['formatting']['enable_zfill'], ['track_number', 'total_tracks', 'disc_number', 'total_discs']
        track_tags = {k: (zfill_lambda(v) if zfill_enabled and k in zfill_list else sanitise_name(v)) for k, v in {**asdict(track_info.tags), **asdict(track_info)}.items()}
        track_tags['explicit'] = ' [E]' if track_info.explicit else ''
        track_tags['artist'] = sanitise_name(track_info.artists[0])  # if len(track_info.artists) == 1 else 'Various Artists'
        codec = track_info.codec

        self.set_indent_number(indent_level)
        self.print(f'=== Downloading track {track_info.name} ({track_id}) ===', drop_level=1)

        if self.download_mode is not DownloadTypeEnum.album and track_info.album: self.print(f'Album: {track_info.album} ({track_info.album_id})')
        if self.download_mode is not DownloadTypeEnum.artist: self.print(f'Artists: {", ".join(track_info.artists)} ({track_info.artist_id})')
        if track_info.release_year: self.print(f'Release year: {track_info.release_year!s}')
        if track_info.duration: self.print(f'Duration: {beauty_format_seconds(track_info.duration)}')
        if self.download_mode is DownloadTypeEnum.track: self.print(f'Service: {self.module_settings[self.service_name].service_name}')

        to_print = 'Codec: ' + codec_data[codec].pretty_name
        if track_info.bitrate: to_print += f', bitrate: {track_info.bitrate!s}kbps'
        if track_info.bit_depth: to_print += f', bit depth: {track_info.bit_depth!s}bit'
        if track_info.sample_rate: to_print += f', sample rate: {track_info.sample_rate!s}kHz'
        self.print(to_print)

        # Check if track_info returns error, display it and return this function to not download the track
        if track_info.error:
            self.print(track_info.error)
            self.print(f'=== Track {track_id} failed ===', drop_level=1)
            return

        album_location = album_location.replace('\\', '/')

        # Ignores "single_full_path_format" and just downloads every track as an album
        if self.global_settings['formatting']['force_album_format'] and self.download_mode in {
            DownloadTypeEnum.track, DownloadTypeEnum.playlist}:
            # Fetch every needed album_info tag and create an album_location
            album_info: AlbumInfo = self.service.get_album_info(track_info.album_id)
            # Save the playlist path to save all the albums in the playlist path
            path = self.path if album_location == '' else album_location
            album_location = self._create_album_location(path, track_info.album_id, album_info)
            album_location = album_location.replace('\\', '/')

            # Download booklet, animated album cover and album cover if present
            self._download_album_files(album_location, album_info)

        if self.download_mode is DownloadTypeEnum.track and not self.global_settings['formatting']['force_album_format']:  # Python 3.10 can't become popular sooner, ugh
            track_location_name = self.path + self.global_settings['formatting']['single_full_path_format'].format(**track_tags)
        elif track_info.tags.total_tracks == 1 and not self.global_settings['formatting']['force_album_format']:
            track_location_name = album_location + self.global_settings['formatting']['single_full_path_format'].format(**track_tags)
        else:
            if track_info.tags.total_discs and track_info.tags.total_discs > 1: album_location += f'CD {track_info.tags.disc_number!s}/'
            track_location_name = album_location + self.global_settings['formatting']['track_filename_format'].format(**track_tags)
        # fix file and path character limit
        track_location_name = fix_file_limit(track_location_name)
        os.makedirs(track_location_name[:track_location_name.rfind('/')], exist_ok=True)

        try:
            conversions = {CodecEnum[k.upper()]: CodecEnum[v.upper()] for k, v in self.global_settings['advanced']['codec_conversions'].items()}
        except:
            conversions = {}
            self.print('Warning: codec_conversions setting is invalid!')
        
        container = codec_data[codec].container
        track_location = f'{track_location_name}.{container.name}'

        check_codec = conversions[track_info.codec] if track_info.codec in conversions else track_info.codec
        check_location = f'{track_location_name}.{codec_data[check_codec].container.name}'

        if os.path.isfile(check_location) and not self.global_settings['advanced']['ignore_existing_files']:
            self.print('Track file already exists')

            # also make sure to add already existing tracks to the m3u playlist
            if m3u_playlist:
                self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

            self.print(f'=== Track {track_id} skipped ===', drop_level=1)
            return

        if track_info.description:
            with open(track_location_name + '.txt', 'w', encoding='utf-8') as f: f.write(track_info.description)

        # Begin process
        print()
        self.print("Downloading track file")
        try:
            download_info: TrackDownloadInfo = self.service.get_track_download(**track_info.download_extra_kwargs)
            download_file(download_info.file_url, track_location, headers=download_info.file_url_headers, enable_progress_bar=True, indent_level=self.oprinter.indent_number) \
                if download_info.download_type is DownloadEnum.URL else shutil.move(download_info.temp_file_path, track_location)

            # check if get_track_download returns a different codec, for example ffmpeg failed
            if download_info.different_codec:
                # overwrite the old known codec with the new
                codec = download_info.different_codec
                container = codec_data[codec].container
                old_track_location = track_location
                # create the new track_location and move the old file to the new location
                track_location = f'{track_location_name}.{container.name}'
                shutil.move(old_track_location, track_location)
        except KeyboardInterrupt:
            self.print('^C pressed, exiting')
            sys.exit(0)
        except Exception:
            if self.global_settings['advanced']['debug_mode']: raise
            self.print('Warning: Track download failed: ' + str(sys.exc_info()[1]))
            self.print(f'=== Track {track_id} failed ===', drop_level=1)
            return

        delete_cover = False
        if not cover_temp_location:
            cover_temp_location = create_temp_filename()
            delete_cover = True
            covers_module_name = self.third_party_modules[ModuleModes.covers]
            covers_module_name = covers_module_name if covers_module_name != self.service_name else None
            if covers_module_name: print()
            self.print('Downloading artwork' + ((' with ' + covers_module_name) if covers_module_name else ''))
            
            jpg_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=self.global_settings['covers']['main_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['main_compression'].lower()])
            ext_cover_options = CoverOptions(file_type=ImageFileTypeEnum[self.global_settings['covers']['external_format']], \
                resolution=self.global_settings['covers']['external_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['external_compression'].lower()])
            
            if covers_module_name:
                default_temp = download_to_temp(track_info.cover_url)
                test_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=get_image_resolution(default_temp), compression=CoverCompressionEnum.high)
                cover_module = self.loaded_modules[covers_module_name]
                rms_threshold = self.global_settings['advanced']['cover_variance_threshold']

                results: list[SearchResult] = self.search_by_tags(covers_module_name, track_info)
                self.print('Covers to test: ' + str(len(results)))
                attempted_urls = []
                for i, r in enumerate(results, start=1):
                    test_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, test_cover_options, **r.extra_kwargs)
                    if test_cover_info.url not in attempted_urls:
                        attempted_urls.append(test_cover_info.url)
                        test_temp = download_to_temp(test_cover_info.url)
                        rms = compare_images(default_temp, test_temp)
                        silentremove(test_temp)
                        self.print(f'Attempt {i} RMS: {rms!s}') # The smaller the root mean square, the closer the image is to the desired one
                        if rms < rms_threshold:
                            self.print('Match found below threshold ' + str(rms_threshold))
                            jpg_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, jpg_cover_options, **r.extra_kwargs)
                            download_file(jpg_cover_info.url, cover_temp_location, artwork_settings=self._get_artwork_settings(covers_module_name))
                            silentremove(default_temp)
                            if self.global_settings['covers']['save_external']:
                                ext_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, ext_cover_options, **r.extra_kwargs)
                                download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(covers_module_name, is_external=True))
                            break
                else:
                    self.print('Third-party module could not find cover, using fallback')
                    shutil.move(default_temp, cover_temp_location)
            else:
                download_file(track_info.cover_url, cover_temp_location, artwork_settings=self._get_artwork_settings())
                if self.global_settings['covers']['save_external'] and ModuleModes.covers in self.module_settings[self.service_name].module_supported_modes:
                    ext_cover_info: CoverInfo = self.service.get_track_cover(track_id, ext_cover_options, **track_info.cover_extra_kwargs)
                    download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(is_external=True))

        if track_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated cover')
            download_file(track_info.animated_cover_url, track_location_name + '_cover.mp4', enable_progress_bar=True)

        # Get lyrics
        embedded_lyrics = ''
        if self.global_settings['lyrics']['embed_lyrics'] or self.global_settings['lyrics']['save_synced_lyrics']:
            lyrics_info = LyricsInfo()
            if self.third_party_modules[ModuleModes.lyrics] and self.third_party_modules[ModuleModes.lyrics] != self.service_name:
                lyrics_module_name = self.third_party_modules[ModuleModes.lyrics]
                self.print('Retrieving lyrics with ' + lyrics_module_name)
                lyrics_module = self.loaded_modules[lyrics_module_name]

                if lyrics_module_name != self.service_name:
                    results: list[SearchResult] = self.search_by_tags(lyrics_module_name, track_info)
                    lyrics_track_id = results[0].result_id if len(results) else None
                    extra_kwargs = results[0].extra_kwargs if len(results) else None
                else:
                    lyrics_track_id = track_id
                    extra_kwargs = {}
                
                if lyrics_track_id:
                    lyrics_info: LyricsInfo = lyrics_module.get_track_lyrics(lyrics_track_id, **extra_kwargs)
                    # if lyrics_info.embedded or lyrics_info.synced:
                    #     self.print('Lyrics retrieved')
                    # else:
                    #     self.print('Lyrics module could not find any lyrics.')
                else:
                    self.print('Lyrics module could not find any lyrics.')
            elif ModuleModes.lyrics in self.module_settings[self.service_name].module_supported_modes:
                lyrics_info: LyricsInfo = self.service.get_track_lyrics(track_id, **track_info.lyrics_extra_kwargs)
                # if lyrics_info.embedded or lyrics_info.synced:
                #     self.print('Lyrics retrieved')
                # else:
                #     self.print('No lyrics available')

            if lyrics_info.embedded and self.global_settings['lyrics']['embed_lyrics']:
                embedded_lyrics = lyrics_info.embedded
            # embed the synced lyrics (f.e. Roon) if they are available
            if lyrics_info.synced and self.global_settings['lyrics']['embed_lyrics'] and \
                    self.global_settings['lyrics']['embed_synced_lyrics']:
                embedded_lyrics = lyrics_info.synced
            if lyrics_info.synced and self.global_settings['lyrics']['save_synced_lyrics']:
                lrc_location = f'{track_location_name}.lrc'
                if not os.path.isfile(lrc_location):
                    with open(lrc_location, 'w', encoding='utf-8') as f:
                        f.write(lyrics_info.synced)

        # Get credits
        credits_list = []
        if self.third_party_modules[ModuleModes.credits] and self.third_party_modules[ModuleModes.credits] != self.service_name:
            credits_module_name = self.third_party_modules[ModuleModes.credits]
            self.print('Retrieving credits with ' + credits_module_name)
            credits_module = self.loaded_modules[credits_module_name]

            if credits_module_name != self.service_name:
                results: list[SearchResult] = self.search_by_tags(credits_module_name, track_info)
                credits_track_id = results[0].result_id if len(results) else None
                extra_kwargs = results[0].extra_kwargs if len(results) else None
            else:
                credits_track_id = track_id
                extra_kwargs = {}
            
            if credits_track_id:
                credits_list = credits_module.get_track_credits(credits_track_id, **extra_kwargs)
                # if credits_list:
                #     self.print('Credits retrieved')
                # else:
                #     self.print('Credits module could not find any credits.')
            # else:
            #     self.print('Credits module could not find any credits.')
        elif ModuleModes.credits in self.module_settings[self.service_name].module_supported_modes:
            self.print('Retrieving credits')
            credits_list = self.service.get_track_credits(track_id, **track_info.credits_extra_kwargs)
            # if credits_list:
            #     self.print('Credits retrieved')
            # else:
            #     self.print('No credits available')
        
        # Do conversions
        old_track_location, old_container = None, None
        if codec in conversions:
            old_codec_data = codec_data[codec]
            new_codec = conversions[codec]
            new_codec_data = codec_data[new_codec]
            self.print(f'Converting to {new_codec_data.pretty_name}')
                
            if old_codec_data.spatial or new_codec_data.spatial:
                self.print('Warning: converting spacial formats is not allowed, skipping')
            elif not old_codec_data.lossless and new_codec_data.lossless and not self.global_settings['advanced']['enable_undesirable_conversions']:
                self.print('Warning: Undesirable lossy-to-lossless conversion detected, skipping')
            elif not old_codec_data and not self.global_settings['advanced']['enable_undesirable_conversions']:
                self.print('Warning: Undesirable lossy-to-lossy conversion detected, skipping')
            else:
                if not old_codec_data.lossless and new_codec_data.lossless:
                    self.print('Warning: Undesirable lossy-to-lossless conversion')
                elif not old_codec_data:
                    self.print('Warning: Undesirable lossy-to-lossy conversion')

                try:
                    conversion_flags = {CodecEnum[k.upper()]:v for k,v in self.global_settings['advanced']['conversion_flags'].items()}
                except:
                    conversion_flags = {}
                    self.print('Warning: conversion_flags setting is invalid, using defaults')
                
                conv_flags = conversion_flags[new_codec] if new_codec in conversion_flags else {}
                temp_track_location = f'{create_temp_filename()}.{new_codec_data.container.name}'
                new_track_location = f'{track_location_name}.{new_codec_data.container.name}'
                
                stream: ffmpeg = ffmpeg.input(track_location, hide_banner=None, y=None)
                # capture_stderr is required for the error output to be captured
                try:
                    # capture_stderr is required for the error output to be captured
                    stream.output(
                        temp_track_location,
                        acodec=new_codec.name.lower(),
                        **conv_flags,
                        loglevel='error'
                    ).run(capture_stdout=True, capture_stderr=True)
                except Error as e:
                    error_msg = e.stderr.decode('utf-8')
                    # get the error message from ffmpeg and search foe the non-experimental encoder
                    encoder = re.search(r"(?<=non experimental encoder ')[^']+", error_msg)
                    if encoder:
                        self.print(f'Encoder {new_codec.name.lower()} is experimental, trying {encoder.group(0)}')
                        # try to use the non-experimental encoder
                        stream.output(
                            temp_track_location,
                            acodec=encoder.group(0),
                            **conv_flags,
                            loglevel='error'
                        ).run()
                    else:
                        # raise any other occurring error
                        raise Exception(f'ffmpeg error converting to {new_codec.name.lower()}:\n{error_msg}')

                # remove file if it requires an overwrite, maybe os.replace would work too?
                if track_location == new_track_location:
                    silentremove(track_location)
                    # just needed so it won't get deleted
                    track_location = temp_track_location

                # move temp_file to new_track_location and delete temp file
                shutil.move(temp_track_location, new_track_location)
                silentremove(temp_track_location)

                if self.global_settings['advanced']['conversion_keep_original']:
                    old_track_location = track_location
                    old_container = container
                else:
                    silentremove(track_location)

                container = new_codec_data.container    
                track_location = new_track_location

        # Add the playlist track to the m3u playlist
        if m3u_playlist:
            self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

        # Finally tag file
        self.print('Tagging file')
        try:
            tag_file(track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                     track_info, credits_list, embedded_lyrics, container)
            if old_track_location:
                tag_file(old_track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                         track_info, credits_list, embedded_lyrics, old_container)
        except TagSavingFailure:
            self.print('Tagging failed, tags saved to text file')
        if delete_cover:
            silentremove(cover_temp_location)
        
        self.print(f'=== Track {track_id} downloaded ===', drop_level=1)

    def _get_artwork_settings(self, module_name = None, is_external = False):
        if not module_name:
            module_name = self.service_name
        return {
            'should_resize': ModuleFlags.needs_cover_resize in self.module_settings[module_name].flags,
            'resolution': self.global_settings['covers']['external_resolution'] if is_external else self.global_settings['covers']['main_resolution'],
            'compression': self.global_settings['covers']['external_compression'] if is_external else self.global_settings['covers']['main_compression'],
            'format': self.global_settings['covers']['external_format'] if is_external else 'jpg'
        }
