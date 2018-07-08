# Aces Rank Extractor

A tool for extracting ranking data from Mario Tennis Aces.

Mario Tennis Aces is an excellent new game from Nintendo. It's got an in-game leaderboard that suits its competitive 
nature. Unfortunately, that leaderboard is inaccessible outside of the game, and no history or statistics about it are 
available. This project aims to fix that.

Aces Rank Extractor extracts the Mario Tennis Aces ranking data at a single point in time. Its input is a video of the
ranking table, as uploaded from a Nintendo Switch, and its output is (well, hopes to be) a collection of database-ready
rows of ranking data.

## Implementation

The idea is

1. Upload a video of scrolling through the ranking table to Twitter using the Switch's capture and video upload
functionality
1. Pull the video using youtube-dl
1. Split the video into frames using ffmpeg
1. Parse each frame for imperfect data using Pillow and tesseract
1. Use a consensus algorithm to derive higher-confidence data from the imperfect data
1. Report the higher-confidence data to a database

And then to make that database accessible via some web UI.

## Setup

1. Install ffmpeg and tesseract on host
1. Set up virtualenv
1. Install requirements
1. Run main.py

## FAQ

* Why not just query their servers for the data?
    * I would love to. Unfortunately, as far as I can tell, the ranking data is behind their game server, which is
    itself behind multiple authentication servers. I haven't got the time to extract the keys required from my Switch
    hardware and game cart to make that authentication happen. Even if I did, my account would probably get flagged
    pretty quickly for scraping. :)

## TODO

* Generate Tesseract training data for leaderboard fonts. Seems to be one for number columns and one for nickname 
column
    * The number column font is close to Nexa Black, but more vertically squished.
* Speed up OCR by parallelizing, or just figuring out a lower bound on OCR FPS that leads to acceptable results

## Disclaimer

Everything is still incredibly rough around the edges, and I have no idea when this project will be at the point of
making data readily available on a website.

I have no affiliation with Nintendo.
