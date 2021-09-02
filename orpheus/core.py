import importlib, json, logging, os, pickle, requests, urllib3, base64, shutil
from datetime import datetime

from orpheus.music_downloader import Downloader
from utils.models import *
from utils.utils import *
from utils.exceptions import *

os.environ['CURL_CA_BUNDLE'] = ''  # Hack to disable SSL errors for requests module for easier debugging
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # Make SSL warnings hidden

# try:
#     time_request = requests.get('https://github.com') # to be replaced with something useful, like an Orpheus updates json
# except:
#     print('Could not reach the internet, quitting')
#     exit()

# timestamp_correction_term = int(datetime.strptime(time_request.headers['Date'], '%a, %d %b %Y %H:%M:%S GMT').timestamp() - datetime.utcnow().timestamp())
# if abs(timestamp_correction_term) > 60*60*24:
#     print('System time is incorrect, using online time to correct it for subscription expiry checks')

timestamp_correction_term = 0

def true_current_utc_timestamp():
    return int(datetime.utcnow().timestamp()) + timestamp_correction_term


class Orpheus:
    def __init__(self, private_mode=False):
        self.extensions, self.extension_list, self.module_list, self.module_settings, self.module_netloc_constants, self.loaded_modules = {}, set(), set(), {}, {}, {}

        self.default_global_settings = {
            "general": {
                "album_search_return_only_albums": False,
                "download_path": "./downloads/",
                "download_quality": "hifi"
            },
            "formatting": {
                "album_format": "{album_name}",
                "playlist_format": "{playlist_name}",
                "artist_format": "{artist_name}/{album_name}",
                "track_filename_format": "{track_number}. {title}",
                "single_full_path_format": "{title}"
            },
            "codecs": {
                "proprietary_codecs": False,
                "spatial_codecs": True
            },
            "module_defaults": {
                "lyrics": "default",
                "covers": "default",
                "credits": "default"
            },
            "lyrics": {
                "embed_lyrics": True,
                "save_synced_lyrics": True
            },
            "covers": {
                "compression": "high",
                "main_resolution": 1400,
                "save_external": False,
                "external_resolution": 3000,
                "external_png": True
            },
            "advanced": {
                "advanced_login_system": False,
                "album_cache_optimisations": True,
                "codec_conversions": {
                    "alac": "flac"
                },
                "conversion_flags": {
                    "flac": {
                        "compression_level": "5"
                    }
                },
                "conversion_save_original": False,
                "cover_variance_threshold": 8,
                "debug_mode": False,
                "disable_subscription_checks": False,
                "enable_undesirable_conversions": False,
                "ignore_existing_files": False,
                "ignore_different_artists": True
            }
        }

        self.settings_location = 'config/settings.json'
        self.session_storage_location = 'config/loginstorage.bin'

        os.makedirs('config') if not os.path.exists('config') else None

        self.settings = json.load(open(self.settings_location,)) if os.path.exists(self.settings_location) else {}

        try:
            logging.basicConfig(level=logging.DEBUG) if self.settings['global']['advanced']['debug_mode'] else None
        except:
            pass

        os.makedirs('extensions') if not os.path.exists('extensions') else None
        for extension in os.listdir('extensions'):  # Loading extensions
            if os.path.isdir(f'extensions/{extension}') and os.path.exists(f'extensions/{extension}/interface.py'):
                class_ = getattr(importlib.import_module(f'extensions.{extension}.interface'), 'OrpheusExtension', None)
                if class_:
                    self.extension_list.add(extension)
                    logging.debug(f'Orpheus: {extension} extension detected')
                else:
                    raise Exception('Error loading extension: "{extension}"')

        # Module preparation (not loaded yet for performance purposes)
        os.makedirs('modules') if not os.path.exists('modules') else None
        module_list = [module.lower() for module in os.listdir('modules') if os.path.exists(f'modules/{module}/interface.py')]
        if not module_list or module_list == ['example']:
            print('No modules are installed, quitting')
            exit()
        logging.debug('Orpheus: Modules detected: ' + ", ".join(module_list))

        for module in module_list:  # Loading module information into module_settings
            module_information: ModuleInformation = getattr(importlib.import_module(f'modules.{module}.interface'), 'module_information', None)
            if module_information and not ModuleFlags.private in module_information.flags and not private_mode:
                self.module_list.add(module)
                self.module_settings[module] = module_information
                logging.debug(f'Orpheus: {module} added as a module')
            else:
                raise Exception(f'Error loading module information from module: "{module}"') # TODO: replace with InvalidModuleError

        duplicates = set()
        for module in self.module_list: # Detecting duplicate url constants
            module_info: ModuleInformation = self.module_settings[module]
            url_constant = module_info.netlocation_constant
            if url_constant:
                if url_constant not in self.module_netloc_constants:
                    self.module_netloc_constants[url_constant] = module
                elif ModuleFlags.private in module_info.flags: # Replacing public modules with private ones
                    duplicates.add(url_constant) if ModuleFlags.private in self.module_settings[url_constant].flags else None
                else:
                    duplicates.add(url_constant)
        
        if duplicates:
            raise Exception('Multiple modules installed that connect to the same service names: ' + ', '.join(duplicates))

        self.update_module_storage()

        for i in self.extension_list:
            extension_settings: ExtensionInformation = getattr(importlib.import_module(f'extensions.{i}.interface'), 'extension_settings', None)
            settings = self.settings['extensions'][extension_settings.extension_type][extension] \
                if extension_settings.extension_type in self.settings['extensions'] \
                and extension in self.settings['extensions'][extension_settings.extension_type] else extension_settings.settings
            extension_type = extension_settings.extension_type
            self.extensions[extension_type] = self.extensions[extension_type] if extension_type in self.extensions else {}
            self.extensions[extension_type][extension] = class_(settings)

        [self.load_module(module) for module in self.module_list if ModuleFlags.startup_load in self.module_settings[module].flags]
        
        self.module_controls = {'module_list': self.module_list, 'module_settings': self.module_settings,
            'loaded_modules': self.loaded_modules, 'module_loader': self.load_module}

    def load_module(self, module: str):
        module = module.lower()
        if module not in self.module_list:
            raise Exception(f'"{module}" does not exist in modules.') # TODO: replace with InvalidModuleError
        if module not in self.loaded_modules:
            class_ = getattr(importlib.import_module(f'modules.{module}.interface'), 'ModuleInterface', None)
            if class_:
                class ModuleError(Exception): # TODO: get rid of this, as it is deprecated
                    def __init__(self, message):
                        super().__init__(module + ' --> ' + str(message))
                
                module_controller = ModuleController(
                    module_settings = self.settings['modules'][module] if module in self.settings['modules'] else None,
                    extensions = self.extensions,
                    temporary_settings_controller = TemporarySettingsController(module, self.session_storage_location),
                    module_error = ModuleError, # DEPRECATED
                    get_current_timestamp = true_current_utc_timestamp,
                    orpheus_options = OrpheusOptions(
                        debug_mode = self.settings['global']['advanced']['debug_mode'],
                        quality_tier = QualityEnum[self.settings['global']['general']['download_quality'].upper()],
                        disable_subscription_check = self.settings['global']['advanced']['disable_subscription_checks'],
                        album_search_return_only_albums = self.settings['global']['general']['album_search_return_only_albums'],
                        album_cache_optimisations = self.settings['global']['advanced']['album_cache_optimisations'],
                        codec_options = CodecOptions(
                            spatial_codecs = self.settings['global']['codecs']['spatial_codecs'],
                            proprietary_codecs = self.settings['global']['codecs']['proprietary_codecs'],
                        ),
                        default_cover_options = CoverOptions(
                            file_type = ImageFileTypeEnum.png if self.settings['global']['covers']['external_png'] else ImageFileTypeEnum.jpg,
                            resolution = self.settings['global']['covers']['main_resolution'],
                            compression = self.settings['global']['covers']['compression']
                        )
                    )
                )

                loaded_module = class_(module_controller)
                self.loaded_modules[module] = loaded_module

                # Check if module has settings
                settings = self.settings['modules'][module] if module in self.settings['modules'] else None
                temporary_session = read_temporary_setting(self.session_storage_location, module)
                if ModuleFlags.standard_login in self.module_settings[module].flags:
                    username = settings['email'] if 'email' in settings else settings['username'] 
                    # Login if simple mode, username login and requested by update_setting_storage
                    if temporary_session and temporary_session['clear_session'] and not self.settings['global']['advanced']['advanced_login_system']:
                        username = settings['email'] if 'email' in settings else settings['username']
                        emailhash = hash_string(username)
                        if temporary_session['emailhash'] != emailhash:
                            print('Logging into ' + self.module_settings[module].service_name)
                            loaded_module.login(username, settings['password'])
                            set_temporary_setting(self.session_storage_location, module, 'emailhash', None, emailhash)
                elif ModuleFlags.jwt_system_enable in self.module_settings[module].flags and temporary_session and \
                        temporary_session['refresh'] and not temporary_session['bearer']:
                    loaded_module.refresh_login()

                logging.debug(f'Orpheus: {module} module has been loaded')
                return loaded_module
            else:
                raise Exception(f'Error loading module: "{module}"') # TODO: replace with InvalidModuleError
        else:
            return self.loaded_modules[module]

    def update_module_storage(self): # Should be refactored eventually
        ## Settings
        old_settings, new_settings, global_settings, extension_settings, module_settings, new_setting_detected = {}, {}, {}, {}, {}, False
        
        for i in ['global', 'extensions', 'modules']:
            old_settings[i] = self.settings[i] if i in self.settings else {}

        for setting_type in self.default_global_settings:
            if setting_type in old_settings['global']:
                global_settings[setting_type] = {}
                for setting in self.default_global_settings[setting_type]:
                    if setting in old_settings['global'][setting_type]:
                        global_settings[setting_type][setting] = old_settings['global'][setting_type][setting]
                    else:
                        global_settings[setting_type][setting] = self.default_global_settings[setting_type][setting]
                        new_setting_detected = True
            else:
                global_settings[setting_type] = self.default_global_settings[setting_type]
                new_setting_detected = True

        for i in self.extension_list:
            extension_information: ExtensionInformation = getattr(importlib.import_module(f'extensions.{i}.interface'), 'extension_settings', None)
            extension_type = extension_information.extension_type
            extension_settings[extension_type] = {} if 'extension_type' not in extension_settings else extension_settings[extension_type]
            old_settings['extensions'][extension_type] = {} if extension_type not in old_settings['extensions'] else old_settings['extensions'][extension_type]
            extension_settings[extension_type][i] = {} # This code regenerates the settings
            for j in extension_information.settings:
                if i in old_settings['extensions'][extension_type] and j in old_settings['extensions'][extension_type][i]:
                    extension_settings[extension_type][i][j] = old_settings['extensions'][extension_type][i][j]
                else:
                    extension_settings[extension_type][i][j] = extension_information.settings[j]
                    new_setting_detected = True

        advanced_login_mode = global_settings['advanced']['advanced_login_system']
        for i in self.module_list:
            module_settings[i] = {} # This code regenerates the settings
            if advanced_login_mode:
                settings_to_parse = self.module_settings[i].global_settings
            else:
                settings_to_parse = {**self.module_settings[i].global_settings, **self.module_settings[i].session_settings}
            if settings_to_parse:
                for j in settings_to_parse:
                    if i in old_settings['modules'] and j in old_settings['modules'][i]:
                        module_settings[i][j] = old_settings['modules'][i][j]
                    else:
                        module_settings[i][j] = settings_to_parse[j]
                        new_setting_detected = True
            else:
                module_settings.pop(i)

        new_settings['global'] = global_settings
        new_settings['extensions'] = extension_settings
        new_settings['modules'] = module_settings

        ## Sessions
        if not os.path.exists(self.session_storage_location):
            pickle.dump({}, open(self.session_storage_location, 'wb'))
        sessions = pickle.load(open(self.session_storage_location, 'rb'))

        if not ('advancedmode' in sessions and 'modules' in sessions and sessions['advancedmode'] == advanced_login_mode):
            sessions = {'advancedmode': advanced_login_mode, 'modules':{}}

        # in format {advancedmode, modules: {modulename: {default, type, sessions: [sessionname: {##}]}}}
        # where ## is 'custom_data':{} plus if jwt 'access, refresh' (+ emailhash in simple)
        # in the special case of simple mode, session is always called default
        new_module_sessions = {}
        for i in self.module_list:
            # Clear storage if type changed
            new_module_sessions[i] = sessions['modules'][i] if i in sessions['modules'] else {'selected':'default', 'sessions':{'default':{}}}

            setting_types = set()
            if ModuleFlags.jwt_system_enable in self.module_settings[i].flags:
                setting_types.add('jwt')
            elif self.module_settings[i].temporary_settings:
                setting_types.add('custom')
            else:
                new_module_sessions.pop(i)
                continue
            
            for current_session in new_module_sessions[i]['sessions'].values():
                # For simple login type only, as it does not apply to advanced login
                clear_session = False

                if ModuleFlags.standard_login in self.module_settings[i].flags and not advanced_login_mode:
                    username = module_settings[i]['email'] if 'email' in module_settings[i] else module_settings[i]['username']
                    if ('emailhash' in current_session and current_session['emailhash'] != hash_string(username)) or ('emailhash' not in current_session):
                        current_session['emailhash'] = ''
                        # Clears email if its hash does not match stored value
                        clear_session = True

                current_session['clear_session'] = clear_session

                if 'jwt' in setting_types:
                    if 'bearer' in current_session and current_session['bearer'] and not clear_session:
                        # Clears bearer token if it's expired
                        try:
                            time_left_until_refresh = json.loads(base64.b64decode(current_session['bearer'].split('.')[0]))['exp'] - true_current_utc_timestamp()
                            current_session['bearer'] = current_session['bearer'] if time_left_until_refresh > 0 else None
                        except:
                            pass
                    else:
                        current_session['bearer'] = None
                        current_session['refresh'] = None
                else:
                    current_session.pop('bearer') if 'bearer' in current_session else None
                    current_session.pop('refreh') if 'refresh' in current_session else None

                # Deletes custom data if the module doesn't exist or adds/removes temporary settings
                if 'custom' in setting_types:
                    current_session['custom_data'] = {} if not 'custom_data' in current_session else current_session['custom_data']
                    new_data = {}
                    for j in self.module_settings[i].temporary_settings:
                        new_data[j] = current_session['custom_data'][j] if 'custom_data' in current_session and j in current_session['custom_data'] and not clear_session else None
                    current_session['custom_data'] = new_data
                else:
                    current_session.pop('custom_data') if 'custom_data' in current_session else None

        pickle.dump({'advancedmode': advanced_login_mode, 'modules': new_module_sessions}, open(self.session_storage_location, 'wb'))
        open(self.settings_location, 'w').write(json.dumps(new_settings, indent = 4, sort_keys = False))

        if new_setting_detected:
            print('New settings detected, or the configuration has been reset. Please update settings.json')
            exit()


def orpheus_core_download(orpheus_session: Orpheus, media_to_download, third_party_modules, separate_download_module, output_path):
    downloader = Downloader(orpheus_session.settings['global'], orpheus_session.module_controls, output_path)
    os.makedirs('temp') if not os.path.exists('temp') else None

    for media in media_to_download:
        mainmodule = media.service_name
        if ModuleModes.download not in orpheus_session.module_settings[mainmodule].module_supported_modes:
            raise Exception(f'{mainmodule} does not support track downloading') # TODO: replace with ModuleDoesNotSupportAbility

        # Load and prepare module
        music = orpheus_session.load_module(mainmodule)
        downloader.service = music
        downloader.service_name = mainmodule

        for i in third_party_modules:
            moduleselected = third_party_modules[i]
            if moduleselected:
                if moduleselected not in orpheus_session.module_list:
                    raise Exception(f'{moduleselected} does not exist in modules.') # TODO: replace with InvalidModuleError
                elif i not in orpheus_session.module_settings[moduleselected].module_supported_modes:
                    raise Exception(f'Module {moduleselected} does not support {i}') # TODO: replace with ModuleDoesNotSupportAbility
                else:
                    # If all checks pass, load up the selected module
                    orpheus_session.load_module(moduleselected)

        downloader.third_party_modules = third_party_modules

        mediatype = media.media_type
        media_id = media.media_id

        downloader.download_mode = mediatype

        # Mode to download playlist using other service
        if separate_download_module != 'default' and separate_download_module != mainmodule:
            if mediatype is not DownloadTypeEnum.playlist:
                raise Exception('The separate download module option is only for playlists.') # TODO: replace with ModuleDoesNotSupportAbility
            downloader.download_playlist(media_id, custom_module = separate_download_module)
        else:  # Standard download modes
            if mediatype is DownloadTypeEnum.album:
                downloader.download_album(media_id)
            elif mediatype is DownloadTypeEnum.track:
                downloader.download_track(media_id)
            elif mediatype is DownloadTypeEnum.playlist:
                downloader.download_playlist(media_id)
            elif mediatype is DownloadTypeEnum.artist:
                downloader.download_artist(media_id)
            else:
                raise Exception(f'\tUnknown media type "{mediatype}"')
        print()

    shutil.rmtree('temp') if os.path.exists('temp') else None