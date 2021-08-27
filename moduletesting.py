#!/usr/bin/env python3

import argparse, cProfile, pstats
from orpheus.core import Orpheus

def main():
    parser = argparse.ArgumentParser(description='Orpheus Module Testing Tool')
    parser.add_argument('-pr', '--private', action='store_true', help='Enable private modules')
    parser.add_argument('-sp', '--save_profile', action='store_true', help='Save profiling for use with SnakeViz')
    parser.add_argument('-pp', '--print_profile', action='store_true', help='Print profiling (long output)')
    parser.add_argument('module')
    parser.add_argument('function')
    parser.add_argument('arguments', nargs='*')
    parsed_args = parser.parse_args()

    try:
        with cProfile.Profile() as pr:
            orpheus = Orpheus(parsed_args.private)
            if parsed_args.module.lower() not in orpheus.module_list:
                raise Exception(f'Module {parsed_args.module} either does not exist or mismatches private mode')
            module_instance = orpheus.load_module(parsed_args.module.lower())
            requested_function = getattr(module_instance, parsed_args.function.lower(), None)
            if not requested_function:
                raise Exception(f'Function {parsed_args.function} does not exist')

            args, kwargs = [], {}
            for i in parsed_args.arguments:
                if '=' in i:
                    item, value = i.split('=')
                    kwargs[item] = value
                else:
                    args.append(i)
            requested_function(*args, **kwargs)
    finally:
        stats = pstats.Stats(pr)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.dump_stats(filename='orpheus_profiling.prof') if parsed_args.save_profile else None
        stats.print_stats() if parsed_args.print_profile else None

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n\t^C pressed - abort')
        exit()