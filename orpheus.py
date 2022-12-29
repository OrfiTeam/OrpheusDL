#!/usr/bin/env python3

import argparse
import re
from urllib.parse import urlparse

from orpheus.core import *
from orpheus.music_downloader import beauty_format_seconds


def main():
    print('''
   ____             _                    _____  _      
  / __ \           | |                  |  __ \| |     
 | |  | |_ __ _ __ | |__   ___ _   _ ___| |  | | |     
 | |  | | '__| '_ \| '_ \ / _ \ | | / __| |  | | |     
 | |__| | |  | |_) | | | |  __/ |_| \__ \ |__| | |____ 
  \____/|_|  | .__/|_| |_|\___|\__,_|___/_____/|______|
             | |                                       
             |_|                                       
             \n''')
    
    help_ = 'Use "settings [option]" for orpheus controls (coreupdate, fullupdate, modinstall), "settings [module]' \
           '[option]" for module specific options (update, test, setup), searching by "[search/luckysearch] [module]' \
           '[track/artist/playlist/album] [query]", or just putting in urls. (you may need to wrap the URLs in double' \
           'quotes if you have issues downloading)'
    parser = argparse.ArgumentParser(description='Orpheus: modular music archival')
    parser.add_argument('-p', '--private', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-o', '--output', help='Select a download output path. Default is the provided download path in config/settings.py')
    parser.add_argument('-lr', '--lyrics', default='default', help='Set module to get lyrics from')
    parser.add_argument('-cv', '--covers', default='default', help='Override module to get covers from')
    parser.add_argument('-cr', '--credits', default='default', help='Override module to get credits from')
    parser.add_argument('-sd', '--separatedownload', default='default', help='Select a different module that will download the playlist instead of the main module. Only for playlists.')
    parser.add_argument('arguments', nargs='*', help=help_)
    args = parser.parse_args()

    orpheus = Orpheus(args.private)
    if not args.arguments:
        parser.print_help()
        exit()

    orpheus_mode = args.arguments[0].lower()
    if orpheus_mode == 'settings': # These should call functions in a separate py file, that does not yet exist
        setting = args.arguments[1].lower()
        if setting == 'refresh':
            print('settings.json has been refreshed successfully.')
            return # Actually the only one that should genuinely return here after doing nothing
        elif setting == 'core_update':  # Updates only Orpheus
            return  # TODO
        elif setting == 'full_update':  # Updates Orpheus and all modules
            return  # TODO
            orpheus.update_setting_storage()
        elif setting == 'module_install':  # Installs a module with git
            return  # TODO
            orpheus.update_setting_storage()
        elif setting == 'test_modules':
            return # TODO
        elif setting in orpheus.module_list:
            orpheus.load_module(setting)
            modulesetting = args.arguments[2].lower()
            if modulesetting == 'update':
                return  # TODO
                orpheus.update_setting_storage()
            elif modulesetting == 'setup':
                return  # TODO
            elif modulesetting == 'adjust_setting':
                return  # TODO
            #elif modulesetting in [custom settings function list] TODO (here so test can be replaced)
            elif modulesetting == 'test': # Almost equivalent to sessions test
                return  # TODO
            else:
                raise Exception(f'Unknown setting "{modulesetting}" for module "{setting}"')
        else:
            raise Exception(f'Unknown setting: "{setting}"')
    elif orpheus_mode == 'sessions':
        module = args.arguments[1].lower()
        if module in orpheus.module_list:
            option = args.arguments[2].lower()
            if option == 'add':
                return  # TODO
            elif option == 'delete':
                return  # TODO
            elif option == 'list':
                return  # TODO
            elif option == 'test':
                session_name = args.arguments[3].lower()
                if session_name == 'all':
                    return  # TODO
                else:
                    return  # TODO, will also have a check for if the requested session actually exists, obviously
            else:
                raise Exception(f'Unknown option {option}, choose add/delete/list/test')
        else:
            raise Exception(f'Unknown module {module}') # TODO: replace with InvalidModuleError
    else:
        path = args.output if args.output else orpheus.settings['global']['general']['download_path']
        if path[-1] == '/': path = path[:-1]  # removes '/' from end if it exists
        os.makedirs(path, exist_ok=True)

        media_types = '/'.join(i.name for i in DownloadTypeEnum)

        if orpheus_mode == 'search' or orpheus_mode == 'luckysearch':
            if len(args.arguments) > 3:
                modulename = args.arguments[1].lower()
                if modulename in orpheus.module_list:
                    try:
                        query_type = DownloadTypeEnum[args.arguments[2].lower()]
                    except KeyError:
                        raise Exception(f'{args.arguments[2].lower()} is not a valid search type! Choose {media_types}')
                    lucky_mode = True if orpheus_mode == 'luckysearch' else False
                    
                    query = ' '.join(args.arguments[3:])
                    module = orpheus.load_module(modulename)
                    items = module.search(query_type, query, limit = (1 if lucky_mode else orpheus.settings['global']['general']['search_limit']))
                    if len(items) == 0:
                        raise Exception(f'No search results for {query_type.name}: {query}')

                    if lucky_mode:
                        selection = 0
                    else:
                        for index, item in enumerate(items, start=1):
                            additional_details = '[E] ' if item.explicit else ''
                            additional_details += f'[{beauty_format_seconds(item.duration)}] ' if item.duration else ''
                            additional_details += f'[{item.year}] ' if item.year else ''
                            additional_details += ' '.join([f'[{i}]' for i in item.additional]) if item.additional else ''
                            if query_type is not DownloadTypeEnum.artist:
                                artists = ', '.join(item.artists) if item.artists is list else item.artists
                                print(f'{str(index)}. {item.name} - {", ".join(artists)} {additional_details}')
                            else:
                                print(f'{str(index)}. {item.name} {additional_details}')
                        
                        selection_input = input('Selection: ')
                        if selection_input.lower() in ['e', 'q', 'x', 'exit', 'quit']: exit()
                        if not selection_input.isdigit(): raise Exception('Input a number')
                        selection = int(selection_input)-1
                        if selection < 0 or selection >= len(items): raise Exception('Invalid selection')
                        print()
                    selected_item: SearchResult = items[selection]
                    media_to_download = {modulename: [MediaIdentification(media_type=query_type, media_id=selected_item.result_id, extra_kwargs=selected_item.extra_kwargs)]}
                elif modulename == 'multi':
                    return  # TODO
                else:
                    modules = [i for i in orpheus.module_list if ModuleFlags.hidden not in orpheus.module_settings[i].flags]
                    raise Exception(f'Unknown module name "{modulename}". Must select from: {", ".join(modules)}') # TODO: replace with InvalidModuleError
            else:
                print(f'Search must be done as orpheus.py [search/luckysearch] [module] [{media_types}] [query]')
                exit() # TODO: replace with InvalidInput
        elif orpheus_mode == 'download':
            if len(args.arguments) > 3:
                modulename = args.arguments[1].lower()
                if modulename in orpheus.module_list:
                    try:
                        media_type = DownloadTypeEnum[args.arguments[2].lower()]
                    except KeyError:
                        raise Exception(f'{args.arguments[2].lower()} is not a valid download type! Choose {media_types}')
                    media_to_download = {modulename: [MediaIdentification(media_type=media_type, media_id=i) for i in args.arguments[3:]]}
                else:
                    modules = [i for i in orpheus.module_list if ModuleFlags.hidden not in orpheus.module_settings[i].flags]
                    raise Exception(f'Unknown module name "{modulename}". Must select from: {", ".join(modules)}') # TODO: replace with InvalidModuleError
            else:
                print(f'Download must be done as orpheus.py [download] [module] [{media_types}] [media ID 1] [media ID 2] ...')
                exit() # TODO: replace with InvalidInput
        else:  # if no specific modes are detected, parse as urls, but first try loading as a list of URLs
            arguments = tuple(open(args.arguments[0], 'r')) if len(args.arguments) == 1 and os.path.exists(args.arguments[0]) else args.arguments
            media_to_download = {}
            for link in arguments:
                if link.startswith('http'):
                    url = urlparse(link)
                    components = url.path.split('/')

                    service_name = None
                    for i in orpheus.module_netloc_constants:
                        if re.findall(i, url.netloc): service_name = orpheus.module_netloc_constants[i]
                    if not service_name:
                        raise Exception(f'URL location "{url.netloc}" is not found in modules!')
                    if service_name not in media_to_download: media_to_download[service_name] = []

                    if orpheus.module_settings[service_name].url_decoding is ManualEnum.manual:
                        module = orpheus.load_module(service_name)
                        media_to_download[service_name].append(module.custom_url_parse(link))
                    else:
                        if not components or len(components) <= 2:
                            print(f'\tInvalid URL: "{link}"')
                            exit() # TODO: replace with InvalidInput
                        
                        url_constants = orpheus.module_settings[service_name].url_constants
                        if not url_constants:
                            url_constants = {
                                'track': DownloadTypeEnum.track,
                                'album': DownloadTypeEnum.album,
                                'playlist': DownloadTypeEnum.playlist,
                                'artist': DownloadTypeEnum.artist
                            }

                        type_matches = [media_type for url_check, media_type in url_constants.items() if url_check in components]

                        if not type_matches:
                            print(f'Invalid URL: "{link}"')
                            exit()

                        media_to_download[service_name].append(MediaIdentification(media_type=type_matches[-1], media_id=components[-1]))
                else:
                    raise Exception(f'Invalid argument: "{link}"')

        # Prepare the third-party modules similar to above
        tpm = {ModuleModes.covers: '', ModuleModes.lyrics: '', ModuleModes.credits: ''}
        for i in tpm:
            moduleselected = getattr(args, i.name).lower()
            if moduleselected == 'default':
                moduleselected = orpheus.settings['global']['module_defaults'][i.name]
            if moduleselected == 'default':
                moduleselected = None
            tpm[i] = moduleselected
        sdm = args.separatedownload.lower()

        if not media_to_download:
            print('No links given')

        orpheus_core_download(orpheus, media_to_download, tpm, sdm, path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n\t^C pressed - abort')
        exit()
