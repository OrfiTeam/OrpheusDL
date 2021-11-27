import base64, logging
from dataclasses import asdict

from mutagen.easymp4 import EasyMP4
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import EasyMP3
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4Cover
from mutagen.mp4 import MP4Tags
from mutagen.id3 import PictureType, APIC, USLT, TDRL
from PIL import Image

from utils.models import ContainerEnum, TrackInfo
from utils.exceptions import *

# Needed for Windows tagging support
MP4Tags._padding = 0


def tag_file(file_path: str, image_path: str, track_info: TrackInfo, credits_list: list, embedded_lyrics: str, container: ContainerEnum):
    # TODO: eliminate tags already in track info
    
    if container == ContainerEnum.flac:
        tagger = FLAC(file_path)
    elif container == ContainerEnum.opus:
        tagger = OggOpus(file_path)
    elif container == ContainerEnum.ogg:
        tagger = OggVorbis(file_path)
    elif container == ContainerEnum.mp3:
        tagger = EasyMP3(file_path)

        # Register encoded, rating, compatible_brands, major_brand and minor_version
        tagger.tags.RegisterTextKey('encoded', 'TSSE')
        tagger.tags.RegisterTXXXKey('compatible_brands', 'compatible_brands')
        tagger.tags.RegisterTXXXKey('major_brand', 'major_brand')
        tagger.tags.RegisterTXXXKey('minor_version', 'minor_version')
        tagger.tags.RegisterTXXXKey('RATING', 'Rating')

        del tagger.tags['encoded']
    elif container == ContainerEnum.m4a:
        tagger = EasyMP4(file_path)
        # Register ISRC, lyrics, cover and explicit tags
        tagger.RegisterTextKey('isrc', '----:com.apple.itunes:ISRC')
        tagger.RegisterTextKey('explicit', 'rtng') if track_info.explicit is not None else None
        tagger.RegisterTextKey('covr', 'covr')
        tagger.RegisterTextKey('lyrics', '\xa9lyr') if embedded_lyrics else None
    else:
        raise Exception('Unknown container for tagging')

    # Remove all useless MPEG-DASH ffmpeg tags
    if 'major_brand' in tagger.tags:
        del tagger.tags['major_brand']
    if 'minor_version' in tagger.tags:
        del tagger.tags['minor_version']
    if 'compatible_brands' in tagger.tags:
        del tagger.tags['compatible_brands']
    if 'encoder' in tagger.tags:
        del tagger.tags['encoder']

    tagger['title'] = track_info.name
    if track_info.album:
        tagger['album'] = track_info.album
    if track_info.tags.album_artist:
        tagger['albumartist'] = track_info.tags.album_artist

    # Only tested for MPEG-4, FLAC and MP3
    if container in {ContainerEnum.m4a, ContainerEnum.flac, ContainerEnum.mp3}:
        tagger['artist'] = track_info.artists
    else:
        tagger['artist'] = track_info.artists[0]

    if container == ContainerEnum.m4a or container == ContainerEnum.mp3:
        if track_info.tags.track_number and track_info.tags.total_tracks:
            tagger['tracknumber'] = str(track_info.tags.track_number) + '/' + str(track_info.tags.total_tracks)
        elif track_info.tags.track_number:
            tagger['tracknumber'] = str(track_info.tags.track_number)
        if track_info.tags.disc_number and track_info.tags.total_discs:
            tagger['discnumber'] = str(track_info.tags.disc_number) + '/' + str(track_info.tags.total_discs)
        elif track_info.tags.disc_number:
            tagger['discnumber'] = str(track_info.tags.disc_number)
    else:
        if track_info.tags.track_number:
            tagger['tracknumber'] = str(track_info.tags.track_number)
        if track_info.tags.disc_number:
            tagger['discnumber'] = str(track_info.tags.disc_number)
        if track_info.tags.total_tracks:
            tagger['totaltracks'] = str(track_info.tags.total_tracks)
        if track_info.tags.total_discs:
            tagger['totaldiscs'] = str(track_info.tags.total_discs)

    if track_info.tags.release_date:
        if container == ContainerEnum.mp3:
            # Never access protected attributes, too bad! Only works on ID3v2.4, disabled for now!
            # tagger.tags._EasyID3__id3._DictProxy__dict['TDRL'] = TDRL(encoding=3, text=track_info.tags.release_date)
            # Fall back to the YEAR tag
            tagger['date'] = str(track_info.release_year)
        else:
            tagger['date'] = track_info.tags.release_date
    else:
        tagger['date'] = str(track_info.release_year)

    if track_info.tags.copyright:
        tagger['copyright'] = track_info.tags.copyright

    if track_info.explicit is not None:
        if container == ContainerEnum.m4a:
            tagger['explicit'] = b'\x01' if track_info.explicit else b'\x02'
        elif container == ContainerEnum.mp3:
            tagger['Rating'] = 'Explicit' if track_info.explicit else 'Clean'
        else:
            tagger['Rating'] = 'Explicit' if track_info.explicit else 'Clean'

    if track_info.tags.genres:
        tagger['genre'] = track_info.tags.genres[0]  # TODO: all of them

    if track_info.tags.isrc:
        if container == ContainerEnum.m4a:
            tagger['isrc'] = track_info.tags.isrc.encode()
        else:
            tagger['isrc'] = track_info.tags.isrc

    # Need to change to merge duplicate credits automatically, or switch to plain dicts instead of list[dataclass]
    # which is currently pointless
    if credits_list:
        if container == ContainerEnum.m4a:
            for credit in credits_list:
                # Create a new freeform atom and set the contributors in bytes
                tagger.RegisterTextKey(credit.type, '----:com.apple.itunes:' + credit.type)
                tagger[credit.type] = [con.encode() for con in credit.names]
        elif container == ContainerEnum.mp3:
            for credit in credits_list:
                # Create a new user-defined text frame key
                tagger.tags.RegisterTXXXKey(credit.type.upper(), credit.type)
                tagger[credit.type] = credit.names
        else:
            for credit in credits_list:
                try:
                    tagger.tags[credit.type] = credit.names
                except:
                    pass

    if embedded_lyrics:
        if container == ContainerEnum.mp3:
            # Never access protected attributes, too bad! I hope I never have to write ID3 code again
            tagger.tags._EasyID3__id3._DictProxy__dict['USLT'] = USLT(
                encoding=3,
                lang=u'eng',  # don't assume?
                text=embedded_lyrics
            )
        else:
            tagger['lyrics'] = embedded_lyrics

    if track_info.tags.replay_gain and track_info.tags.replay_peak and container != ContainerEnum.m4a:
        tagger['REPLAYGAIN_TRACK_GAIN'] = str(track_info.tags.replay_gain)
        tagger['REPLAYGAIN_TRACK_PEAK'] = str(track_info.tags.replay_peak)

    with open(image_path, 'rb') as c:
        data = c.read()

    picture = Picture()
    picture.data = data

    # Check if cover is smaller than 16MB
    if len(picture.data) < picture._MAX_SIZE:
        if container == ContainerEnum.flac:
            picture.type = PictureType.COVER_FRONT
            picture.mime = u'image/jpeg'
            tagger.add_picture(picture)
        elif container == ContainerEnum.m4a:
            tagger['covr'] = [MP4Cover(data, imageformat=MP4Cover.FORMAT_JPEG)]
        elif container == ContainerEnum.mp3:
            # Never access protected attributes, too bad!
            tagger.tags._EasyID3__id3._DictProxy__dict['APIC'] = APIC(
                encoding=3,  # UTF-8
                mime='image/jpeg',
                type=3,  # album art
                desc='Cover',  # name
                data=data
            )
        # If you want to have a cover in only a few applications, then this technically works for Opus
        elif container == ContainerEnum.ogg or container == ContainerEnum.opus:
            im = Image.open(image_path)
            width, height = im.size
            picture.type = 17
            picture.desc = u'Cover Art'
            picture.mime = u'image/jpeg'
            picture.width = width
            picture.height = height
            picture.depth = 24
            encoded_data = base64.b64encode(picture.write())
            tagger['metadata_block_picture'] = [encoded_data.decode('ascii')]

    else:
        print('\tCover file size is too large, only {0:.2f}MB are allowed. '
              'Track will not have cover saved.'.format(picture._MAX_SIZE / 1024 ** 2))

    try:
        tagger.save(file_path, v2_version=3, v23_sep=None) if container == ContainerEnum.mp3 else tagger.save(file_path)
    except:
        logging.debug('Tagging failed.')
        tag_text = '\n'.join((f'{k}: {v}' for k, v in asdict(track_info.tags).items() if v and k != 'credits' and k != 'lyrics'))
        tag_text += '\n\ncredits:\n    ' + '\n    '.join(f'{credit.type}: {", ".join(credit.names)}' for credit in credits_list if credit.names) if credits_list else ''
        tag_text += '\n\nlyrics:\n    ' + '\n    '.join(embedded_lyrics.split('\n')) if embedded_lyrics else ''
        open(file_path.rsplit('.', 1)[0] + '_tags.txt', 'w').write(tag_text)
        raise TagSavingFailure
