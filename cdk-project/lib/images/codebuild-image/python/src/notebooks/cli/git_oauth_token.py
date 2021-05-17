#!/usr/bin/env python3

import notebooks.git


def main():
    git = notebooks.git.Git()
    print(git.oauth_token)  # This returns the string to bash scripts calling this python script


if __name__ == "__main__":
    main()
