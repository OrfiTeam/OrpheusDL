import base64, logging
from dataclasses import asdict

from mutagen.easymp4 import EasyMP4
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import EasyMP3
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4Cover
from mutagen.mp4 import MP4Tags
from mutagen.id3 import PictureType
from PIL import Image

from utils.models import Tags, ContainerEnum
from utils.exceptions import *

# Needed for Windows tagging support
MP4Tags._padding = 0


def tag_file(file_path: str, image_path: str, tags: Tags, container: ContainerEnum):
    if container == ContainerEnum.flac:
        tagger = FLAC(file_path)
    elif container == ContainerEnum.opus:
        tagger = OggOpus(file_path)
    elif container == ContainerEnum.ogg:
        tagger = OggVorbis(file_path)
    elif container == ContainerEnum.mp3:
        tagger = EasyMP3(file_path)
    elif container == ContainerEnum.m4a:
        tagger = EasyMP4(file_path)
        # Register ISRC, lyrics, cover and explicit tags
        tagger.RegisterTextKey('isrc', '----:com.apple.itunes:ISRC')
        tagger.RegisterTextKey('explicit', 'rtng') if tags.explicit is not None else None
        tagger.RegisterTextKey('covr', 'covr')
        tagger.RegisterTextKey('lyrics', '\xa9lyr') if tags.lyrics else None
    else:
        raise Exception('Unknown container for tagging')

    tagger['title'] = tags.title
    if tags.album:
        tagger['album'] = tags.album
    if tags.album_artist:
        tagger['albumartist'] = tags.album_artist
    if tags.artist:
        tagger['artist'] = tags.artist

    if container == ContainerEnum.m4a or container == ContainerEnum.mp3:
        if tags.track_number and tags.total_tracks:
            tagger['tracknumber'] = str(tags.track_number) + '/' + str(tags.total_tracks)
        elif tags.track_number:
            tagger['tracknumber'] = str(tags.track_number)
        if tags.disc_number and tags.total_discs:
            tagger['discnumber'] = str(tags.disc_number) + '/' + str(tags.total_discs)
        elif tags.disc_number:
            tagger['discnumber'] = str(tags.disc_number)
    else:
        if tags.track_number:
            tagger['tracknumber'] = str(tags.track_number)
        if tags.disc_number:
            tagger['discnumber'] = str(tags.disc_number)
        if tags.total_tracks:
            tagger['totaltracks'] = str(tags.total_tracks)
        if tags.total_discs:
            tagger['totaldiscs'] = str(tags.total_discs)

    tagger['date'] = str(tags.date)

    if tags.copyright:
        tagger['copyright'] = tags.copyright

    if tags.explicit is not None:
        if container == ContainerEnum.m4a:
            tagger['explicit'] = b'\x01' if tags.explicit else b'\x02'
        elif container != ContainerEnum.mp3:
            tagger['Rating'] = 'Explicit' if tags.explicit else 'Clean'

    if tags.genre:
        tagger['genre'] = tags.genre

    if tags.isrc:
        if container == ContainerEnum.m4a:
            tagger['isrc'] = tags.isrc.encode()
        else:
            tagger['isrc'] = tags.isrc

    # Need to change to merge dupicate credits automatically, or switch to plain dicts instead of list[dataclass] which is currently pointless
    if tags.credits:
        if container == ContainerEnum.m4a:
            for credit in tags.credits:
                # Create a new freeform atom and set the contributors in bytes
                tagger.RegisterTextKey(credit.type, '----:com.apple.itunes:' + credit.type)
                tagger[credit.type] = [con.encode() for con in credit.names]
        else:
            for credit in tags.credits:
                try:
                    tagger.tags[credit.type] = credit.names
                except:
                    pass

    if tags.lyrics:
       tagger['lyrics'] = tags.lyrics

    if tags.replay_gain and tags.replay_peak and container != ContainerEnum.m4a:
        tagger['REPLAYGAIN_TRACK_GAIN'] = str(tags.replay_gain)
        tagger['REPLAYGAIN_TRACK_PEAK'] = str(tags.replay_peak)

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
            # tagger.add(id3.APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=data))
            pass
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
        tagger.save(file_path)
    except:
        logging.debug('Tagging failed.')
        tag_text = '\n'.join((f'{k}: {v}' for k, v in asdict(tags).items() if v and k != 'credits' and k != 'lyrics'))
        tag_text += '\n\ncredits:\n    ' + '\n    '.join(f'{credit.type}: {", ".join(credit.names)}' for credit in tags.credits if credit.names) if tags.credits else ''
        tag_text += '\n\nlyrics:\n    ' + '\n    '.join(tags.lyrics.split('\n')) if tags.lyrics else ''
        open(file_path.rsplit('.', 1)[0] + '_tags.txt', 'w').write(tag_text)
        raise TagSavingFailure