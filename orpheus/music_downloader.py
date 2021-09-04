import logging, os, ffmpeg
from dataclasses import asdict

from orpheus.tagging import tag_file
from utils.models import *
from utils.utils import *
from utils.exceptions import *


#TODO: use stuff in https://realpython.com/python-formatted-output
class Downloader:
    def __init__(self, settings, module_controls, path):
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

        self.oprinter = Oprinter()
        self.print = self.oprinter.oprint
        self.set_indent_number = self.oprinter.set_indent_number

    def search_by_tags(self, module_name, tags):
        return self.loaded_modules[module_name].search(DownloadTypeEnum.track, '{title} {artist}'.format(**asdict(tags)), tags=tags)

    def download_playlist(self, playlist_id, custom_module=None):
        self.set_indent_number(1)

        # returns in form {playlist_name, playlist_creator_name, playlist_creator_id, tracks:[track_id]}
        playlist_info: PlaylistInfo = self.service.get_playlist_info(playlist_id)
        self.print(f'=== Downloading playlist {playlist_info.playlist_name} ({playlist_id}) ===', drop_level=1)
        if playlist_info.playlist_creator_id:
            self.print(f'Playlist creator: {playlist_info.playlist_creator_name} ({playlist_info.playlist_creator_id})')
        else:
            self.print(f'Playlist creator: {playlist_info.playlist_creator_name}')
        number_of_tracks = len(playlist_info.tracks)
        self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')

        # Clean up playlist tags
        playlist_tags = {k: sanitise_name(v) for k, v in asdict(playlist_info).items()}
        path = self.path + self.global_settings['formatting']['playlist_format'].format(**playlist_tags) + '/'
        os.makedirs(path) if not os.path.exists(path) else None
        cover_path = f'{path}Cover.{playlist_info.cover_type}'
        if playlist_info.cover_url:
            self.print('Downloading playlist cover')
            download_file(playlist_info.cover_url, cover_path)

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
                track_info: TrackInfo = self.loaded_modules[original_service].get_track_info(track_id)
                
                self.service = self.loaded_modules[custom_module]
                self.service_name = custom_module
                results = self.search_by_tags(custom_module, track_info.tags)
                track_id = results[0].result_id if len(results) else None
                
                if track_id:
                    self.download_track(track_id, album_location=path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2)
                else:
                    if ModuleModes.download in self.module_settings[original_service].module_supported_modes:
                        self.service = self.loaded_modules[original_service]
                        self.service_name = original_service
                        self.print(f'Track {track_info.track_name} not found, using the original service as a fallback', drop_level=1)
                        tracks_errored.add(f'{track_info.track_name} - {track_info.artist_name}')
                        self.download_track(track_id, album_location=path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2)
                    else:
                        self.print(f'Track {track_info.track_name} not found, skipping')
        else:
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                self.download_track(track_id, album_location=path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2)

        self.set_indent_number(1)
        self.print(f'=== Playlist {playlist_info.playlist_name} downloaded ===', drop_level=1)

        logging.debug('Failed tracks: ' + ', '.join(tracks_errored)) if tracks_errored else None

    def download_album(self, album_id: str, artist_name: str = None, indent_level: int = 1):
        self.set_indent_number(indent_level)

        # Returns in form {album_name, artist_name, artist_id, tracks:[track_id]}
        album_info: AlbumInfo = self.service.get_album_info(album_id)
        if not album_info:
            return
        number_of_tracks = len(album_info.tracks)

        # Clean up album tags
        album_tags = {k: sanitise_name(v) for k, v in asdict(album_info).items()}
        if artist_name:
            album_tags['artist_name'] = artist_name
            path = self.path + self.global_settings['formatting']['artist_format'].format(**album_tags) + '/'
        else:
            path = self.path + self.global_settings['formatting']['album_format'].format(**album_tags) + '/'
        os.makedirs(path) if not os.path.exists(path) else None

        cover_path = f'{path}Cover.{album_info.cover_type}'
        if album_info.cover_url:
            self.print('Downloading album cover')
            download_file(album_info.cover_url, cover_path)
        
        
        if album_info.booklet_url:
            self.print('Downloading booklet')
            download_file(album_info.booklet_url, path + 'Booklet.pdf') if album_info.booklet_url and not os.path.exists(path + 'Booklet.pdf') else None

        if number_of_tracks > 1:
            if self.download_mode is DownloadTypeEnum.album:
                self.set_indent_number(1)
            elif self.download_mode is DownloadTypeEnum.artist:
                self.set_indent_number(2)

            self.print(f'=== Downloading album {album_info.album_name} ({album_id}) ===', drop_level=1)
            self.print(f'Artist: {album_info.artist_name} ({album_info.artist_id})')
            self.print(f'Number of tracks: {number_of_tracks!s}')
            self.print(f'Service: {self.module_settings[self.service_name].service_name}')

            for index, track_id in enumerate(album_info.tracks, start=1):
                self.set_indent_number(indent_level + 1)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                self.download_track(track_id, album_location=path, track_index=index, number_of_tracks=number_of_tracks, main_artist=artist_name, indent_level=indent_level+1)

            self.set_indent_number(indent_level)
            self.print(f'=== Album {album_info.album_name} downloaded ===', drop_level=1)

        elif number_of_tracks == 1:
            self.download_track(album_info.tracks[0], album_location=path, track_index=None, number_of_tracks=1, main_artist=artist_name, indent_level=indent_level)
        else:
            raise Exception('Album has no tracks')

    def download_artist(self, artist_id: str):
        # Returns in form {artist_name, albums:album_id]}
        artist_info: ArtistInfo = self.service.get_artist_info(artist_id)
        artist_name = artist_info.artist_name

        self.set_indent_number(1)

        self.print(f'=== Downloading artist {artist_name} ({artist_id}) ===', drop_level=1)
        self.print(f'Number of albums: {len(artist_info.albums)!s}')
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')

        number_of_albums = len(artist_info.albums)

        for index, album_id in enumerate(artist_info.albums, start=1):
            self.set_indent_number(2)
            print()
            self.print(f'Album {index}/{number_of_albums}', drop_level=1)
            self.download_album(album_id, artist_name=artist_name, indent_level=2)

        self.set_indent_number(1)
        self.print(f'=== Artist {artist_name} downloaded ===', drop_level=1)

    def download_track(self, track_id: str, album_location: str = None, main_artist: str = '', track_index: int = 0, number_of_tracks: int = 0, indent_level: int = 1):
        track_info: TrackInfo = self.service.get_track_info(track_id)
        # if track_info.artist_name.lower() != main_artist.lower() and self.global_settings['advanced']['ignore_different_artists'] and self.download_mode is DownloadTypeEnum.artist:
        #    self.print('Track is not from the correct artist, skipping', drop_level=1)
        #    return
        
        if number_of_tracks and track_index:
            track_info.tags.track_number = track_index
            track_info.tags.total_tracks = number_of_tracks
        zfill_number = len(str(track_info.tags.total_tracks)) if self.download_mode is not DownloadTypeEnum.track else 1
        zfill_lambda = lambda input : sanitise_name(str(input)).zfill(zfill_number) if input is not None else None

        # Separate copy of tags for formatting purposes
        track_tags = {k: (zfill_lambda(v) if k in ['track_number', 'total_tracks', 'disc_number', 'total_discs'] else sanitise_name(v)) for k, v in asdict(track_info.tags).items()}
        track_name = track_tags['title']
        codec = track_info.codec
        container = codec_data[codec].container

        self.set_indent_number(indent_level)
        self.print(f'=== Downloading track {track_name} ({track_id}) ===', drop_level=1)

        if self.download_mode is DownloadTypeEnum.track:
            track_location_name = self.path + self.global_settings['formatting']['single_full_path_format'].format(**track_tags)
        else:
            album_location = album_location.replace('\\', '/')
            album_location += 'CD' + track_info.tags.disc_number if track_info.tags.total_discs and int(track_info.tags.total_discs) > 1 else ''
            os.makedirs(album_location) if not os.path.exists(album_location) and album_location else None
            track_location_name = album_location + self.global_settings['formatting']['track_filename_format'].format(**track_tags)
        
        track_location = f'{track_location_name}.{container.name}'
        if os.path.isfile(track_location) and not self.global_settings['advanced']['ignore_existing_files']:
            self.print('Track file already exists', drop_level=1)
            self.print(f'=== Track {track_id} skipped ===', drop_level=1)
            return

        if self.download_mode is not DownloadTypeEnum.album and track_info.album_name:
            self.print(f'Album: {track_info.album_name} ({track_info.album_id})')
        if self.download_mode is not DownloadTypeEnum.album and self.download_mode is not DownloadTypeEnum.artist and track_info.artist_name:
            self.print(f'Artist: {track_info.artist_name} ({track_info.artist_id})')
        if self.download_mode is DownloadTypeEnum.track:
            self.print(f'Service: {self.module_settings[self.service_name].service_name}')

        to_print = 'Codec: ' + codec_data[codec].pretty_name
        to_print += f', bitrate: {track_info.bitrate}kbps' if track_info.bitrate else ''
        to_print += f', bit depth: {track_info.bit_depth}bit' if track_info.bit_depth else ''
        to_print += f', sample rate: {track_info.sample_rate}kHz' if track_info.sample_rate else ''
        self.print(to_print)

        if track_info.codec in [CodecEnum.EAC3, CodecEnum.MHA1, CodecEnum.AC4] and not self.global_settings['codecs']['spatial_codecs']:
            self.print('Spatial codecs are disabled, if you want to download it, set "spatial_codecs": true')
            return None

        if track_info.codec in [CodecEnum.MQA] and not self.global_settings['codecs']['spatial_codecs']:
            self.print('Proprietary codecs are disabled, if you want to download it, set "proprietary_codecs": true')
            return None

        # Begin process
        self.print("Downloading track file")
        try:
            if track_info.download_type is DownloadEnum.URL:
                download_file(track_info.file_url, track_location, headers=track_info.file_url_headers, enable_progress_bar=True, indent_level=self.oprinter.indent_number)
            elif track_info.download_type is DownloadEnum.TEMP_FILE_PATH:
                temp_location = self.service.get_track_tempdir(track_id)
                os.rename(temp_location, track_location)
        except:
            self.print('Warning: Track download failed')
            return

        cover_temp_location = create_temp_filename()
        cover_compression = CoverCompressionEnum[self.global_settings['covers']['compression'].lower()]
        jpg_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=self.global_settings['covers']['main_resolution'], compression=cover_compression)
        ext_cover_options = CoverOptions(file_type=ImageFileTypeEnum.png if self.global_settings['covers']['external_png'] else ImageFileTypeEnum.jpg, \
            resolution=self.global_settings['covers']['external_resolution'], compression=cover_compression)

        print()
        covers_module_name = self.third_party_modules[ModuleModes.covers]
        self.print('Downloading artwork' + (' with ' + covers_module_name if covers_module_name else ''))
        if covers_module_name:
            default_temp = download_to_temp(track_info.cover_url)
            test_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=get_image_resolution(default_temp), compression=CoverCompressionEnum.high)
            cover_module = self.loaded_modules[covers_module_name]
            rms_threshold = self.global_settings['advanced']['cover_variance_threshold']

            results = self.search_by_tags(covers_module_name, track_info.tags)
            self.print('Covers to test: ' + str(len(results)))
            attempted_urls = []
            for i, r in enumerate(results, start=1):
                test_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, test_cover_options)
                if test_cover_info.url not in attempted_urls:
                    attempted_urls.append(test_cover_info.url)
                    test_temp = download_to_temp(test_cover_info.url)
                    rms = compare_images(default_temp, test_temp)
                    silentremove(test_temp)
                    self.print(f'Attempt {i} RMS: {rms!s}') # The smaller the root mean square, the closer the image is to the desired one
                    if rms < rms_threshold:
                        self.print('Match found below threshold ' + str(rms_threshold))
                        jpg_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, jpg_cover_options)
                        download_file(jpg_cover_info.url, cover_temp_location)
                        silentremove(default_temp)
                        if self.global_settings['covers']['save_external']:
                            ext_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, ext_cover_options)
                            download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}')
                        break
            else:
                self.print('Third-party module could not find cover, using fallback')
                os.rename(default_temp, cover_temp_location)
        elif ModuleModes.covers in self.module_settings[self.service_name].module_supported_modes:
            main_cover_info: CoverInfo = self.service.get_track_cover(track_id, jpg_cover_options)
            download_file(main_cover_info.url, cover_temp_location)
            if self.global_settings['covers']['save_external']:
                ext_cover_info: CoverInfo = self.service.get_track_cover(track_id, ext_cover_options)
                download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}')
        else:
            download_file(track_info.cover_url, cover_temp_location)

        # Get lyrics
        if self.global_settings['lyrics']['embed_lyrics'] or self.global_settings['lyrics']['save_synced_lyrics']:
            lyrics_info = LyricsInfo()
            if track_info.tags.lyrics:
                self.print('Embedded tags already provided by main module, however this is not recommended behaviour')
            elif self.third_party_modules[ModuleModes.lyrics]:
                lyrics_module_name = self.third_party_modules[ModuleModes.lyrics]
                self.print('Retrieving lyrics with ' + lyrics_module_name)
                lyrics_module = self.loaded_modules[lyrics_module_name]

                if lyrics_module_name != self.service_name:
                    results = self.search_by_tags(lyrics_module_name, track_info.tags)
                    lyrics_track_id = results[0].result_id if len(results) else None
                else:
                    lyrics_track_id = self.track_id
                
                if lyrics_track_id:
                    lyrics_info: LyricsInfo = lyrics_module.get_track_lyrics(lyrics_track_id)
                    # if lyrics_info.embedded or lyrics_info.synced:
                    #     self.print('Lyrics retrieved')
                    # else:
                    #     self.print('Lyrics module could not find any lyrics.')
                else:
                    self.print('Lyrics module could not find any lyrics.')
            elif ModuleModes.lyrics in self.module_settings[self.service_name].module_supported_modes:
                lyrics_info: LyricsInfo = self.service.get_track_lyrics(track_id)

                # if lyrics_info.embedded or lyrics_info.synced:
                #     self.print('Lyrics retrieved')
                # else:
                #     self.print('No lyrics available')

            if lyrics_info.embedded and self.global_settings['lyrics']['embed_lyrics']:
                track_info.tags.lyrics = lyrics_info.embedded
            if lyrics_info.synced and self.global_settings['lyrics']['save_synced_lyrics']:
                lrc_location = f'{track_location_name}.lrc'
                if not os.path.isfile(lrc_location):
                    with open(lrc_location, 'w') as f:
                        f.write(lyrics_info.synced)

        # Get credits
        if track_info.tags.credits:
            self.print('Credits already provided by main module, however this is not recommended behaviour')
        elif self.third_party_modules[ModuleModes.credits]:
            credits_module_name = self.third_party_modules[ModuleModes.credits]
            self.print('Retrieving credits with ' + credits_module_name)
            credits_module = self.loaded_modules[credits_module_name]

            if credits_module_name != self.service_name:
                results = self.search_by_tags(credits_module_name, track_info.tags)
                credits_track_id = results[0].result_id if len(results) else None
            else:
                credits_track_id = self.track_id
            
            if credits_track_id:
                credits_list = credits_module.get_track_credits(credits_track_id)
                if credits_list:
                    # self.print('Credits retrieved')
                    track_info.tags.credits = credits_list
                # else:
                #     self.print('Credits module could not find any credits.')
            # else:
            #     self.print('Credits module could not find any credits.')
        elif ModuleModes.credits in self.module_settings[self.service_name].module_supported_modes:
            self.print('Retrieving credits')
            credits_list = self.service.get_track_credits(track_id)
            if credits_list:
                # self.print('Credits retrieved')
                track_info.tags.credits = credits_list
            # else:
            #     self.print('No credits available')

        try:
            conversions = {CodecEnum[k.upper()]: CodecEnum[v.upper()] for k, v in self.global_settings['advanced']['codec_conversions'].items()}
        except:
            conversions = {}
            self.print('Warning: codec_conversions setting is invalid!')
        
        # Do conversions
        save_original, new_track_location = True, None
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
                new_track_location = f'{track_location_name}.{new_codec_data.container.name}'
                
                stream = ffmpeg.input(track_location, hide_banner=None, y=None)
                stream.output(new_track_location, acodec=new_codec.name.lower(), **conv_flags, loglevel='error').run()

                if not self.global_settings['advanced']['conversion_save_original']:
                    silentremove(track_location)
                    save_original = False

        # Finally tag file
        self.print('Tagging file')
        try:
            tag_file(track_location, cover_temp_location, track_info.tags, container) if save_original else None
            tag_file(new_track_location, cover_temp_location, track_info.tags, new_codec_data.container) if new_track_location else None
        except TagSavingFailure:
            self.print('Tagging failed, tags saved to text file')
        silentremove(cover_temp_location)

        self.print(f'=== Track {track_id} downloaded ===', drop_level=1)


class Oprinter: # Could change to inherit from print class instead, but this is fine
    def __init__(self):
        self.indent_number = 1
        self.printing_enabled = True

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

    def oprint(self, input: str, drop_level: int = 0):
        if self.printing_enabled:
            print(' ' * (self.indent_number - drop_level * self.multiplier) + input)