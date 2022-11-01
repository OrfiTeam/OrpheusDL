import pickle, requests, errno, hashlib, math, os, re, operator
from tqdm import tqdm
from PIL import Image, ImageChops
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import reduce


def hash_string(input_str: str, hash_type: str = 'MD5'):
    if hash_type == 'MD5':
        return hashlib.md5(input_str.encode("utf-8")).hexdigest()
    else:
        raise Exception('Invalid hash type selected')

def create_requests_session():
    session_ = requests.Session()
    retries = Retry(total=10, backoff_factor=0.4, status_forcelist=[429, 500, 502, 503, 504])
    session_.mount('http://', HTTPAdapter(max_retries=retries))
    session_.mount('https://', HTTPAdapter(max_retries=retries))
    return session_

sanitise_name = lambda name : re.sub(r'[:]', ' - ', re.sub(r'[\\/*?"<>|$]', '', re.sub(r'[ \t]+$', '', str(name).rstrip()))) if name else ''


def fix_file_limit(path: str, file_limit=250):
    # only needs the relative path, the abspath uses already existing folders
    rel_path = os.path.relpath(path).replace('\\', '/')
    # iterate over all folders and file and check for a file_limit violation
    split_path = [folder[:file_limit] if len(folder) > file_limit else folder for folder in rel_path.split('/')]
    # join the split_path together
    return '/'.join(split_path)


r_session = create_requests_session()

def download_file(url, file_location, headers={}, enable_progress_bar=False, indent_level=0, artwork_settings=None):
    if os.path.isfile(file_location):
        return None

    r = r_session.get(url, stream=True, headers=headers, verify=False)

    total = None
    if 'content-length' in r.headers:
        total = int(r.headers['content-length'])

    try:
        with open(file_location, 'wb') as f:
            if enable_progress_bar and total:
                try:
                    columns = os.get_terminal_size().columns
                    if os.name == 'nt':
                        bar = tqdm(total=total, unit='B', unit_scale=True, unit_divisor=1024, initial=0, miniters=1, ncols=(columns-indent_level), bar_format=' '*indent_level + '{l_bar}{bar}{r_bar}')
                    else:
                        raise
                except:
                    bar = tqdm(total=total, unit='B', unit_scale=True, unit_divisor=1024, initial=0, miniters=1, bar_format=' '*indent_level + '{l_bar}{bar}{r_bar}')
                # bar.set_description(' '*indent_level)
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        bar.update(len(chunk))
                bar.close()
            else:
                [f.write(chunk) for chunk in r.iter_content(chunk_size=1024) if chunk]
        if artwork_settings and artwork_settings.get('should_resize', False):
            new_resolution = artwork_settings.get('resolution', 1400)
            new_format = artwork_settings.get('format', 'jpeg')
            if new_format == 'jpg': new_format = 'jpeg'
            new_compression = artwork_settings.get('compression', 'low')
            if new_compression == 'low':
                new_compression = 90
            elif new_compression == 'high':
                new_compression = 70
            if new_format == 'png': new_compression = None
            with Image.open(file_location) as im:
                im = im.resize((new_resolution, new_resolution), Image.Resampling.BICUBIC)
                im.save(file_location, new_format, quality=new_compression)
    except KeyboardInterrupt:
        if os.path.isfile(file_location):
            print(f'\tDeleting partially downloaded file "{str(file_location)}"')
            silentremove(file_location)
        raise KeyboardInterrupt

# root mean square code by Charlie Clark: https://code.activestate.com/recipes/577630-comparing-two-images/
def compare_images(image_1, image_2):
    with Image.open(image_1) as im1, Image.open(image_2) as im2:
        h = ImageChops.difference(im1, im2).convert('L').histogram()
        return math.sqrt(reduce(operator.add, map(lambda h, i: h*(i**2), h, range(256))) / (float(im1.size[0]) * im1.size[1]))

# TODO: check if not closing the files causes issues, and see if there's a way to use the context manager with lambda expressions
get_image_resolution = lambda image_location : Image.open(image_location).size[0]

def silentremove(filename):
    try:
        os.remove(filename)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

def read_temporary_setting(settings_location, module, root_setting=None, setting=None, global_mode=False):
    temporary_settings = pickle.load(open(settings_location, 'rb'))
    module_settings = temporary_settings['modules'][module] if module in temporary_settings['modules'] else None
    
    if module_settings:
        if global_mode:
            session = module_settings
        else:
            session = module_settings['sessions'][module_settings['selected']]
    else:
        session = None

    if session and root_setting:
        if setting:
            return session[root_setting][setting] if root_setting in session and setting in session[root_setting] else None
        else:
            return session[root_setting] if root_setting in session else None
    elif root_setting and not session:
        raise Exception('Module does not use temporary settings') 
    else:
        return session

def set_temporary_setting(settings_location, module, root_setting, setting=None, value=None, global_mode=False):
    temporary_settings = pickle.load(open(settings_location, 'rb'))
    module_settings = temporary_settings['modules'][module] if module in temporary_settings['modules'] else None

    if module_settings:
        if global_mode:
            session = module_settings
        else:
            session = module_settings['sessions'][module_settings['selected']]
    else:
        session = None

    if not session:
        raise Exception('Module does not use temporary settings')
    if setting:
        session[root_setting][setting] = value
    else:
        session[root_setting] = value
    pickle.dump(temporary_settings, open(settings_location, 'wb'))

create_temp_filename = lambda : f'temp/{os.urandom(16).hex()}'

def save_to_temp(input: bytes):
    location = create_temp_filename()
    open(location, 'wb').write(input)
    return location

def download_to_temp(url, headers={}, extension='', enable_progress_bar=False, indent_level=0):
    location = create_temp_filename() + (('.' + extension) if extension else '')
    download_file(url, location, headers=headers, enable_progress_bar=enable_progress_bar, indent_level=indent_level)
    return location