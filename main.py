from PIL import Image, ImageDraw
import pytesseract

import subprocess
import os
import itertools
from collections import Counter
import time

TEST_VIDEO_PATH = "/Users/owner/repos/aces-scraper/resources/acesranks-01.mp4"
IDENTIFIER_STRIP_X = 37
IDENTIFIER_STRIP_Y_START = 97
IDENTIFIER_STRIP_Y_END = 655


def get_row_type(identifier_strip_rgb_triplet):
    red, green, blue = identifier_strip_rgb_triplet
    rgb_sum = red + green + blue

    if rgb_sum < 40:
        return "heading"
    elif red > 140:
        return "personal"
    elif rgb_sum < 140:
        return "dark"
    else:
        return "light"


class LeaderboardRowBounds:
    def __init__(self, row_type, y_start, y_end):
        self.row_type = row_type
        self.y_start = y_start
        self.y_end = y_end


def extract_row_classes_and_bounds(rgb_image, identifier_strip_x, identifier_strip_y_start, identifier_strip_y_end):
    """

    :param rgb_image:
    :param identifier_strip_x:
    :param identifier_strip_y_start:
    :param identifier_strip_y_end:
    :return: [ classified row bounds ] ; [ ClassifiedRowBounds ]
    """
    # { y: (r, g, b) }; { int: (int, int, int) }
    ys_and_rgbs = { strip_y: rgb_image.getpixel((identifier_strip_x, strip_y))
                    for strip_y in range(identifier_strip_y_start, identifier_strip_y_end+1) }

    # { y: row type } ; { int: str }
    ys_and_row_types = { y: get_row_type(rgb)
                         for y, rgb in ys_and_rgbs.items() }

    ranking_rows = list() # [ ClassifiedRowBounds ]

    sorted_y_values_and_row_types = sorted(ys_and_row_types.items(), key=lambda tup: tup[0])
    max_y = sorted_y_values_and_row_types[-1][0]
    traversing_row_type = sorted_y_values_and_row_types[0][1]
    row_start_y = sorted_y_values_and_row_types[0][0]
    row_end_y = row_start_y

    for y, row_type in sorted_y_values_and_row_types:
        if row_type == traversing_row_type:
            if y < max_y:
                # continuing a row
                row_end_y = y
            else:
                # this is the very last item we're traversing.
                # make sure we append whatever last row we've been working on!
                ranking_rows.append(LeaderboardRowBounds(traversing_row_type, row_start_y, row_end_y))

        else:
            # we're transitioning from one row type to another.
            # first, append the row that we just finished
            ranking_rows.append(LeaderboardRowBounds(traversing_row_type, row_start_y, row_end_y + 1))

            # then, initialize the bounds of the new row
            row_start_y = y
            row_end_y = y
            traversing_row_type = row_type

    return ranking_rows


def identify_row_bounds(image):
    """
    Identify all of the rows in a snapshot from Mario Tennis Aces' rankings board.

    :param output_path: where to store the marked up image.
    :return:
    """
    # Get the RGB values of each pixel in the identifier strip
    rgb_image = image.convert('RGB')

    classified_row_bounds_list = extract_row_classes_and_bounds(rgb_image,
                                                                IDENTIFIER_STRIP_X,
                                                                IDENTIFIER_STRIP_Y_START,
                                                                IDENTIFIER_STRIP_Y_END)
    # for classified_row_bounds in classified_row_bounds_list:
    #     print("{} row: pixels [{}, {}]".format(classified_row_bounds.row_type,
    #                                            classified_row_bounds.y_start,
    #                                            classified_row_bounds.y_end))

    return classified_row_bounds_list


def dump_marked_image(source_image, row_bounds_list, output_path):
    ROW_TYPES_TO_COLORS = {
        "heading": (255, 255, 0),
        "light": (102, 255, 51),
        "dark": (255, 0, 255),
        "personal": (0, 255, 255)
    }

    # Initialize an output image
    image_with_bounding_boxes = source_image.copy()

    # Mark it up
    # TODO: Magic numbers
    for row_bounds in row_bounds_list:
        draw = ImageDraw.Draw(image_with_bounding_boxes)
        draw.rectangle(((31, row_bounds.y_start + 1), (1219, row_bounds.y_end - 1)),
                       outline=ROW_TYPES_TO_COLORS[row_bounds.row_type])

    image_with_bounding_boxes.save(output_path)


class LeaderboardRow():
    def __init__(self, ranking, character, country, nickname, points, wins_losses, win_percent, rating):
        self.ranking = ranking
        self.character = character
        self.country = country
        self.nickname = nickname
        self.points = points
        self.wins_losses = wins_losses
        self.win_percent = win_percent
        self.rating = rating


def filter_extractable_bounds(raw_bounds_list):
    """
    Given a list of row bounds, filter out those from which we cannot realistically extract quality data.

    :param raw_bounds_list:
    :return:
    """
    return [ raw_bounds for raw_bounds in raw_bounds_list if raw_bounds.y_end - raw_bounds.y_start >= 40 ]


# TODO: Maybe another intermediate format that keys by ranking. Would allow consensus algorithm that could work with
# imperfect rows, e.g. if one row has ranking 4 and nickname X and points unknown and another row has ranking 4 and
# nickname unknown and points Y, could combine into ranking 4 and nickname X and points Y
def ocr_row(image, row_bounds):
    """

    :param image:
    :param row_bounds:
    :return: None, or LeaderboardRow with all fields Noneable except for ranking.
    """
    # Crop each cell out.
    RANKING_START_X = IDENTIFIER_STRIP_X
    RANKING_END_X = 161
    NICKNAME_START_X = 288
    NICKNAME_END_X = 548
    POINTS_START_X = 554
    POINTS_END_X = 732
    WINS_LOSSES_START_X = 738
    WINS_LOSSES_END_X = 934
    WIN_PERCENT_START_X = 935
    WIN_PERCENT_END_X = 1020
    RATING_START_X = 1024
    RATING_END_X = 1218

    # convert the image to black and white before passing to tesseract - seems to help OCR
    image_bw = image.convert("L")

    # debug
    image_bw.copy().save("/tmp/poop.png")

    ranking_image = image_bw.crop((RANKING_START_X, row_bounds.y_start, RANKING_END_X, row_bounds.y_end))
    nickname_image = image_bw.crop((NICKNAME_START_X, row_bounds.y_start, NICKNAME_END_X, row_bounds.y_end))
    points_image = image_bw.crop((POINTS_START_X, row_bounds.y_start, POINTS_END_X, row_bounds.y_end))
    wins_losses_image = image_bw.crop((WINS_LOSSES_START_X, row_bounds.y_start, WINS_LOSSES_END_X, row_bounds.y_end))
    win_percent_image = image_bw.crop((WIN_PERCENT_START_X, row_bounds.y_start, WIN_PERCENT_END_X, row_bounds.y_end))
    rating_image = image_bw.crop((RATING_START_X, row_bounds.y_start, RATING_END_X, row_bounds.y_end))

    # PSM 7 means "treat the image as a single text line"

    raw_ranking = pytesseract.image_to_string(ranking_image,
                                              config="--psm 7 -c tessedit_char_whitelist=0123456789",
                                              lang="eng")

    # God help us with the nickname. Is there any pattern to the language / character set?
    raw_nickname = pytesseract.image_to_string(nickname_image,
                                               config="--psm 7",
                                               lang="eng")

    raw_points = pytesseract.image_to_string(points_image,
                                             config="--psm 7 -c tessedit_char_whitelist=0123456789,",
                                             lang="eng")

    raw_wins_losses = pytesseract.image_to_string(wins_losses_image,
                                                  config="--psm 7 -c tessedit_char_whitelist=0123456789-",
                                                  lang="eng")

    raw_win_percent = pytesseract.image_to_string(win_percent_image,
                                                  config="--psm 7 -c tessedit_char_whitelist=0123456789%",
                                                  lang="eng")

    raw_rating = pytesseract.image_to_string(rating_image,
                                             config="--psm 7 -c tessedit_char_whitelist=0123456789",
                                             lang="eng")

    # TODO: Identify country and nickname using a custom image classifier

    # Do basic text cleanup and throw away clearly wrong data
    ranking = raw_ranking.strip()
    if len(ranking) < 1:
        ranking = None
        # No key! Useless row, at least for now.
        return None

    nickname = raw_nickname
    points = raw_points.strip()
    if points.startswith(",") or points.endswith(","):
        points = None
    # TODO: Do we want to separate wins from losses here? Or later?
    # Doing it here would be easier
    wins_losses = raw_wins_losses.strip()
    if wins_losses.startswith("-") or wins_losses.endswith("-"):
        wins_losses = None
    win_percent = raw_win_percent.strip()
    if not win_percent.endswith("%") or win_percent.count("%") != 1:
        win_percent = None
    rating = raw_rating.strip()

    raw_row = LeaderboardRow(ranking, None, None, nickname, points, wins_losses, win_percent, rating)

    return raw_row


def extract_leaderboard_rows_from_image(image):
    all_bounds = identify_row_bounds(image)
    extractable_bounds_list = filter_extractable_bounds(all_bounds)
    leaderboard_rows = [ ocr_row(image, extractable_bounds) for extractable_bounds in extractable_bounds_list ]

    return leaderboard_rows


def reach_leaderboard_consensus(all_incomplete_leaderboard_rows):
    # Group rows by ranking
    # TODO: Need to convert ranking strs to ints for this to be useful?
    sorted_incomplete_leaderboard_rows = sorted(all_incomplete_leaderboard_rows, key=lambda r: r.ranking)
    incomplete_row_groups = itertools.groupby(sorted_incomplete_leaderboard_rows, key=lambda r: r.ranking)

    for ranking, incomplete_row_group_iterable in incomplete_row_groups:
        incomplete_row_group = list(incomplete_row_group_iterable)
        nicknames = [ r.nickname for r in incomplete_row_group if r.nickname is not None ]
        points = [ r.points for r in incomplete_row_group if r.points is not None ]
        wins_losses = [ r.wins_losses for r in incomplete_row_group if r.wins_losses is not None ]
        win_percents = [ r.win_percent for r in incomplete_row_group if r.win_percent is not None ]
        ratings = [ r.rating for r in incomplete_row_group if r.rating is not None ]

        if len(nicknames) < 1 or len(points) < 1 or len(wins_losses) < 1 or len(win_percents) < 1 or len(ratings) < 1:
            # Not one instance of a row contained a certain column
            print("Unable to extract something for ranking {}".format(ranking))
            # TODO: Throw an error?
            continue

        nickname_of_choice = max(Counter(nicknames).items(), key=lambda tup: tup[1])[0]
        print("seeya")


def extract_all_incomplete_leaderboard_rows_from_frames(video_frame_images):
    num_frames_extracted_from = 0
    all_incomplete_rows_from_all_frames = list()
    for video_frame_image in video_frame_images:
        # TODO: This is really slow. Consider parallelizing it. Would be really easy with subprocess module.
        all_incomplete_rows_from_all_frames.extend(extract_leaderboard_rows_from_image(video_frame_image))
        num_frames_extracted_from += 1
        if num_frames_extracted_from % 5 == 0:
            print("Extracted from {} frames...".format(num_frames_extracted_from))
            break

    # TODO: Implement a consensus algorithm that uses the incomplete rows to make
    # Just group the incomplete rows by rank, then take the most common of each present (non-None) value

    return all_incomplete_rows_from_all_frames


def extract_frames(video_path, temp_dir):
    """
    Extract all frames from a given video into individual image files, writing them to a temporary directory.

    :param video_path: Location of video in filesystem.
    :return: List of paths to extracted frames.
    """
    # TODO: Consider using an ffmpeg wrapper. Might be cleaner, and would make dep on ffmpeg more explicit.
    ffmpeg_output_dir = os.path.join(temp_dir, os.path.basename(video_path))
    ffmpeg_output_pattern = os.path.join(ffmpeg_output_dir, "out%06d.png")
    os.makedirs(ffmpeg_output_dir, exist_ok=True)

    # Run ffmpeg
    # subprocess.check_call(["ffmpeg", "-i", video_path, ffmpeg_output_path])
    # TODO: -ss here is a hack to ignore non-leaderboard frames
    subprocess.check_call(["ffmpeg", "-i", video_path, "-ss", "00:00:09", ffmpeg_output_pattern])

    # TODO: This could be problematic if some files existed in the output directory already; it would return those
    # files as well. Consider adding a random string to the output path.
    filenames = os.listdir(ffmpeg_output_dir)
    frame_paths = [ os.path.join(ffmpeg_output_dir, filename) for filename in filenames ]

    return frame_paths


def extract_leaderboard_data_from_video(video_path):
    video_frame_paths = extract_frames(video_path, "/tmp/frames")

    # Load the extracted frames into Pillow images
    # We could use an iterator here if we wanted to save memory... probably doesn't matter since our input videos are
    # thirty seconds long
    video_frames = [ Image.open(video_frame_path) for video_frame_path in video_frame_paths ]

    # TODO: Filter out non-leaderboard frames, or make sure that the video does not have any
    all_incomplete_leaderboard_rows = extract_all_incomplete_leaderboard_rows_from_frames(video_frames)

    high_confidence_leaderboard_rows = reach_leaderboard_consensus(all_incomplete_leaderboard_rows)

    return high_confidence_leaderboard_rows


if __name__ == '__main__':
    data = extract_leaderboard_data_from_video(TEST_VIDEO_PATH)

    print("bye")