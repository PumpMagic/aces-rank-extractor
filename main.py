from PIL import Image, ImageDraw
import pytesseract

import subprocess
import os

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
    def __init__(self, ranking, character, country, nickname, points, wins, losses, win_percent, rating):
        self.ranking = ranking
        self.character = character
        self.country = country
        self.nickname = nickname
        self.points = points
        self.wins = wins
        self.losses = losses
        self.win_percent = win_percent
        self.rating = rating


def filter_extractable_bounds(raw_bounds_list):
    return [ raw_bounds for raw_bounds in raw_bounds_list if raw_bounds.y_end - raw_bounds.y_start >= 40 ]


# TODO: Maybe another intermediate format that keys by ranking. Would allow consensus algorithm that could work with
# imperfect rows, e.g. if one row has ranking 4 and nickname X and points unknown and another row has ranking 4 and
# nickname unknown and points Y, could combine into ranking 4 and nickname X and points Y
def ocr_row(image, row_bounds):
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

    ranking_image = image.crop((RANKING_START_X, row_bounds.y_start, RANKING_END_X, row_bounds.y_end))

    ranking_image.copy().convert("L").save("/tmp/poop.png")

    raw_ranking = pytesseract.image_to_string(ranking_image.convert("L"),
                                              config="--psm 7 -c tessedit_char_whitelist=0123456789",
                                              lang="eng")

    if raw_ranking.strip() == "":
        print("Wow")

    stubbed = LeaderboardRow(raw_ranking, "", "", "", "", "", "", "", "")

    return stubbed


def extract_leaderboard_rows_from_image(image):
    all_bounds = identify_row_bounds(image)
    extractable_bounds_list = filter_extractable_bounds(all_bounds)
    leaderboard_rows = [ ocr_row(image, extractable_bounds) for extractable_bounds in extractable_bounds_list ]

    return leaderboard_rows


def extract_all_leaderboard_rows_from_frames(video_frame_images):
    all_raw_rows = list()

    for video_frame_image in video_frame_images:
        all_raw_rows.append(extract_leaderboard_rows_from_image(video_frame_image))

    return all_raw_rows


def extract_frames(video_path, temp_dir):
    """

    :param video_path:
    :return: list of frame paths
    """
    # TODO: Use a wrapper maybe
    ffmpeg_output_dir = os.path.join(temp_dir, os.path.basename(video_path))
    ffmpeg_output_pattern = os.path.join(ffmpeg_output_dir, "out%04d.png")
    os.makedirs(ffmpeg_output_dir, exist_ok=True)
    # subprocess.check_call(["ffmpeg", "-i", video_path, ffmpeg_output_path])
    # TODO: -ss here is a hack to ignore non-leaderboard frames
    subprocess.check_call(["ffmpeg", "-i", video_path, "-ss", "00:00:09", ffmpeg_output_pattern])

    filenames = os.listdir(ffmpeg_output_dir)
    frame_paths = [ os.path.join(ffmpeg_output_dir, filename) for filename in filenames ]

    return frame_paths


def extract_leaderboard_data_from_video(video_path):
    video_frame_paths = extract_frames(video_path, "/tmp/frames")
    video_frames = [ Image.open(video_frame_path) for video_frame_path in video_frame_paths ]
    # TODO: Filter out non-leaderboard frames, or make sure that the video does not have any
    all_leaderboard_rows = extract_all_leaderboard_rows_from_frames(video_frames)
    leaderboard_rows = reach_leaderboard_consensus(raw_leaderboard_rows)

    return leaderboard_rows


if __name__ == '__main__':
    data = extract_leaderboard_data_from_video(TEST_VIDEO_PATH)

    print("bye")