#!/usr/bin/env python3

import sagemakerci.git


def main():
    git = sagemakerci.git.Git()
    print(git.oauth_token)  # This returns the string to bash scripts calling this python script


if __name__ == "__main__":
    main()
