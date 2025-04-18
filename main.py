
##### TRY RUNNING THIS CODE PLS
# import cv2
# import numpy as np
# import datetime
# import math
# import csv
# import os
# import glob
# # Mask the difference of the 2 images to leave only the moving parts
# def get_mask(frame1, frame2):
#     frame_diff = cv2.subtract(frame2, frame1)
#     frame_diff = cv2.medianBlur(frame_diff, 3)
#     mask = cv2.adaptiveThreshold(
#         frame_diff, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
#         cv2.THRESH_BINARY_INV, 11, 4)
#     mask = cv2.medianBlur(mask, 3)
#     mask = cv2.morphologyEx(
#         mask, cv2.MORPH_CLOSE, np.array((29, 29), dtype=np.uint8))
#     _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)
#     return mask
# # Contrast enhancement for circle detection
# def enhance_contrast(gray):
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
#     return clahe.apply(gray)
# # Find the jellyfish center and radius
# def findJellyCircle(img):
#     previous_circles = None
#     while True:
#         gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
#         gray = cv2.medianBlur(gray, 71)
#         enhanced = enhance_contrast(gray)
#         circles = cv2.HoughCircles(
#             enhanced,
#             cv2.HOUGH_GRADIENT,
#             dp=1.2,
#             minDist=20,
#             param1=30,
#             param2=18,
#             minRadius=30,
#             maxRadius=100)
#         if circles is None:
#             print("No circles detected, using previous circles")
#             circles = previous_circles
#             if circles is None:
#                 return [gray.shape[0] // 2, gray.shape[1] // 2], 50
#         else:
#             circles = np.uint16(np.around(circles))
#             previous_circles = circles
#         jellyCenter = [circles[0][0][1], circles[0][0][0]]
#         radius = circles[0][0][2] + 5
#         return jellyCenter, radius
# # Write the data
# def write(filename, data):
#     with open(f"output/{filename}/{filename}_Results.csv", mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(data)
#
# def extractFrames(video, filename, totalFrame, totalTime, vidnum):
#     currentFrame = 0
#     last = []
#     numNotMoving = 0
#     frames = []
#     movers = []
#     movementCenters = []
#     found = False
#     numSaved = 0
#     # Global maximum, if needed
#     max_jelly_area = 0
#     max_jelly_data = None
#
#     # NEW: Use a block size of 72,000 frames
#     block_max_area = 0  # Maximum jelly area in the current 72,000-frame block.
#     block_max_data = None  # Will store (frame_image, jellyCenter, jellyRadius, currentFrame)
#     previous_block_max_area = None  # Maximum jelly area in the previous block; None for the first block.
#
#     min_separation = 0.4 * user_input  # frames between valid pulse detections
#
#     while True:
#         ret, cur = video.read()
#         if not ret:
#             break
#         frames.append(cur.copy())
#         frames = frames[-15:].copy()  # keep only the last 15 frames
#         cur = cv2.cvtColor(cur, cv2.COLOR_RGB2GRAY)
#
#         if currentFrame > 3:
#             mask = get_mask(cur, last)
#             jellyCenter, jellyRadius = findJellyCircle(frames[-1])
#             jelly_area = math.pi * (jellyRadius ** 2)
#
#             # NEW: Update block maximum for the current 72,000-frame block.
#             if jelly_area > block_max_area:
#                 block_max_area = jelly_area
#                 block_max_data = (cur.copy(), jellyCenter, jellyRadius, currentFrame)  # record current data
#
#             # NEW: Check if we're at the beginning of a new 72,000-frame block.
#             if currentFrame % 72000 == 0:
#                 if currentFrame != 0:
#                     previous_block_max_area = block_max_area
#                     print(f"Block ending at frame {currentFrame - 1}: block_max_area = {previous_block_max_area:.2f}")
#                     # NEW: Save the frame that had the maximum jelly area in this block.
#                     if block_max_data is not None:
#                         frame_img, center, radius, frame_idx = block_max_data
#                         colored_img = cv2.cvtColor(frame_img, cv2.COLOR_GRAY2BGR)
#                         cv2.circle(colored_img, (int(center[1]), int(center[0])), int(radius), (0, 0, 255), 2)
#                         # Build output path using the same base folder as CSV output.
#                         output_dir = os.path.join("output", filename)
#                         os.makedirs(output_dir, exist_ok=True)
#                         image_output_path = os.path.join(output_dir, f"{filename}_Block{currentFrame // 72000}_max.jpg")
#                         cv2.imwrite(image_output_path, colored_img)
#                         print(f"Saved block max image to: {image_output_path}")
#                 else:
#                     previous_block_max_area = None  # Base case for first 72,000 frames.
#                 # Reset block maximum for the new block.
#                 block_max_area = 0
#                 block_max_data = None
#
#             movement_threshold = (0.05 * jelly_area)
#             if np.sum(mask) > movement_threshold:
#                 if numNotMoving > 3:
#                     places = list(zip(*np.where(mask == 255)))
#                     xs = [i[0] for i in places]
#                     ys = [i[1] for i in places]
#                     if np.std(xs) + np.std(ys) < 50:
#                         medX = np.median(xs)
#                         medY = np.median(ys)
#                         minDist = 10000
#                         center = -1
#                         for i in places:
#                             dist = np.sqrt((i[0] - medX) ** 2 + (i[1] - medY) ** 2)
#                             if dist < minDist:
#                                 minDist = dist
#                                 center = i
#                         jellyCenter, jellyRadius = findJellyCircle(frames[-4])
#                         jellyRadius = int(jellyRadius)
#                         dvert = int(jellyCenter[0] - center[0])
#                         dhor = int(center[1] - jellyCenter[1])
#                         movement_distance_sq = dhor ** 2 + dvert ** 2
#                         lower_bound = (jellyRadius * 0.95) ** 2
#                         upper_bound = (jellyRadius * 1.15) ** 2
#                         # Use pulse threshold with 0.9*previous block max area (if applicable).
#                         pulse_threshold_ok = (previous_block_max_area is None) or (
#                                     jelly_area >= 0.9 * previous_block_max_area)
#
#                         if pulse_threshold_ok and lower_bound < movement_distance_sq < upper_bound and \
#                                 (len(movers) == 0 or currentFrame - movers[-1] > min_separation):
#                             delta = datetime.timedelta(
#                                 seconds=video.get(cv2.CAP_PROP_POS_MSEC) / 1000)
#                             write(filename, [
#                                 currentFrame,
#                                 totalFrame + currentFrame,
#                                 jellyCenter[0],
#                                 jellyCenter[1],
#                                 jellyRadius,
#                                 vidnum,
#                                 totalTime + delta,
#                                 center[0],
#                                 center[1]
#                             ])
#                             movers.append(currentFrame)
#                             movementCenters.append(center)
#                             found = True
#                             numNotMoving = 0
#                         else:
#                             numNotMoving += 1
#                     else:
#                         numNotMoving += 1
#                 else:
#                     numNotMoving += 1
#             else:
#                 numNotMoving += 1
#         currentFrame += 1
#         last = cur.copy()
#         # Uncomment the following for testing only:
#         # if currentFrame >= 1000:
#         #     break
#     print(f"Finished processing {filename}.")
#     return currentFrame
import cv2
import numpy as np
import datetime
import math
import csv
import os
import glob
from collections import deque

# ### NEW: Precompute a morphological kernel for the mask function.
# Instead of creating an array on every call, we create it once.
MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))


# Your existing functions for get_mask and enhance_contrast could also be optimized similarly.
def get_mask(frame1, frame2):
    frame_diff = cv2.subtract(frame2, frame1)
    frame_diff = cv2.medianBlur(frame_diff, 3)
    mask = cv2.adaptiveThreshold(
        frame_diff, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 4)
    mask = cv2.medianBlur(mask, 3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, MORPH_KERNEL)
    _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)
    return mask


def enhance_contrast(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def findJellyCircle(img):
    previous_circles = None
    while True:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.medianBlur(gray, 71)
        enhanced = enhance_contrast(gray)
        circles = cv2.HoughCircles(
            enhanced,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=20,
            param1=30,
            param2=18,
            minRadius=30,
            maxRadius=100)
        if circles is None:
            print("No circles detected, using previous circles")
            circles = previous_circles
            if circles is None:
                return [gray.shape[0] // 2, gray.shape[1] // 2], 50
        else:
            circles = np.uint16(np.around(circles))
            previous_circles = circles
        jellyCenter = [circles[0][0][1], circles[0][0][0]]
        radius = circles[0][0][2] + 5
        return jellyCenter, radius


def write(filename, data):
    out_dir = os.path.join("output", filename)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{filename}_Results.csv"), mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data)


# ---------------------------
# Updated extractFrames function with efficiency improvements
# ---------------------------
def extractFrames(video, filename, totalFrame, totalTime, vidnum):
    currentFrame = 0
    numNotMoving = 0
    # ### NEW: Preallocate a fixed-length buffer for the last 15 frames.
    frame_buffer = deque(maxlen=15)
    last_gray = None  # to store the last grayscale frame
    movers = []
    movementCenters = []
    found = False
    # For block-based maximum area tracking:
    block_max_area = 0  # Maximum jelly area in current block.
    block_max_data = None  # (frame_image, jellyCenter, jellyRadius, currentFrame)
    previous_block_max_area = None  # For block thresholding; None in the first block.
    # For your use, we now save a block image every 72000 frames.
    min_separation = 0.4 * user_input  # frames between valid pulse detections

    while True:
        ret, cur = video.read()
        if not ret:
            break

        # ### NEW: Append the new frame into our fixed-length buffer.
        frame_buffer.append(cur.copy())

        # Pre-resize the frame conversion: Do the color conversion only once.
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_RGB2GRAY)

        # Update the last_gray frame (for use in get_mask) after converting once.
        if last_gray is None:
            last_gray = cur_gray.copy()

        # Only use the last 15 frames from the buffer if available.
        if len(frame_buffer) < 15:
            # Continue until we have a full buffer.
            currentFrame += 1
            last_gray = cur_gray.copy()
            continue

        # Use the last frame from our buffer (no slicing of list needed)
        buffer_frame = cv2.cvtColor(frame_buffer[-1], cv2.COLOR_RGB2GRAY)
        # Get mask: Notice we use last_gray as previous frame and current cur_gray.
        mask = get_mask(cur_gray, last_gray)

        # Use buffer_frame for circle detection.
        jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-1])
        jelly_area = math.pi * (jellyRadius ** 2)

        # ### NEW: Update block maximum for the current 72,000-frame block.
        if jelly_area > block_max_area:
            block_max_area = jelly_area
            # Save a copy of the current grayscale frame (avoid repeated conversion)
            block_max_data = (cur_gray.copy(), jellyCenter, jellyRadius, currentFrame)

        # Check if we're at the beginning of a new 72,000-frame block.
        if currentFrame % 72000 == 0:
            if currentFrame != 0:
                previous_block_max_area = block_max_area
                print(f"Block ending at frame {currentFrame - 1}: block_max_area = {previous_block_max_area:.2f}")
                # ### NEW: Save the frame with the maximum jelly area for this block.
                if block_max_data is not None:
                    frame_img, center, radius, frame_idx = block_max_data
                    colored_img = cv2.cvtColor(frame_img, cv2.COLOR_GRAY2BGR)
                    cv2.circle(colored_img, (int(center[1]), int(center[0])), int(radius), (0, 0, 255), 2)
                    output_dir = os.path.join("output", filename)
                    os.makedirs(output_dir, exist_ok=True)
                    image_output_path = os.path.join(output_dir, f"{filename}_Block{currentFrame // 72000}_max.jpg")
                    cv2.imwrite(image_output_path, colored_img)
                    print(f"Saved block max image to: {image_output_path}")
            else:
                previous_block_max_area = None
            # Reset for the new block.
            block_max_area = 0
            block_max_data = None

        movement_threshold = (0.05 * jelly_area)
        if np.sum(mask) > movement_threshold:
            if numNotMoving > 3:
                places = list(zip(*np.where(mask == 255)))
                xs = [pt[0] for pt in places]
                ys = [pt[1] for pt in places]
                if np.std(xs) + np.std(ys) < 50:
                    medX = np.median(xs)
                    medY = np.median(ys)
                    minDist = 10000
                    center_pt = None
                    for pt in places:
                        dist = np.sqrt((pt[0] - medX) ** 2 + (pt[1] - medY) ** 2)
                        if dist < minDist:
                            minDist = dist
                            center_pt = pt
                    # Use a slightly earlier frame from the buffer to recalc the circle
                    jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-4])
                    jellyRadius = int(jellyRadius)
                    dvert = int(jellyCenter[0] - center_pt[0])
                    dhor = int(center_pt[1] - jellyCenter[1])
                    movement_distance_sq = dhor ** 2 + dvert ** 2
                    lower_bound = (jellyRadius * 0.95) ** 2
                    upper_bound = (jellyRadius * 1.15) ** 2
                    pulse_threshold_ok = (previous_block_max_area is None) or (
                                jelly_area >= 0.9 * previous_block_max_area)
                    if pulse_threshold_ok and lower_bound < movement_distance_sq < upper_bound and \
                            (len(movers) == 0 or currentFrame - movers[-1] > min_separation):
                        delta = datetime.timedelta(seconds=video.get(cv2.CAP_PROP_POS_MSEC) / 1000)
                        write(filename, [
                            currentFrame,
                            totalFrame + currentFrame,
                            jellyCenter[0],
                            jellyCenter[1],
                            jellyRadius,
                            vidnum,
                            totalTime + delta,
                            center_pt[0],
                            center_pt[1]
                        ])
                        movers.append(currentFrame)
                        movementCenters.append(center_pt)
                        found = True
                        numNotMoving = 0
                    else:
                        numNotMoving += 1
                else:
                    numNotMoving += 1
            else:
                numNotMoving += 1
        else:
            numNotMoving += 1

        currentFrame += 1
        # Save current grayscale frame for next iteration's mask calculation.
        last_gray = cur_gray.copy()
        # Uncomment the following for testing only:
        # if currentFrame >= 20000:
        #     break

    print(f"Finished processing {filename}.")
    return currentFrame


# Starting program
video_directory = "data/"
video_files = glob.glob(os.path.join(video_directory, "*.mp4"))
video_files += glob.glob(os.path.join(video_directory, "*.avi"))
video_files += glob.glob(os.path.join(video_directory, "*.mov"))
video_files += glob.glob(os.path.join(video_directory, "*.mkv"))
video_files.sort()
totalFrame = 0
totalTime = datetime.datetime.now()
user_input = input("Please enter fps of the video: ")
print("You entered:", user_input)
user_input = float(user_input)
for vidnum, video_file in enumerate(video_files, start=1):
    filename = os.path.splitext(os.path.basename(video_file))[0]
    output_dir = f"output/{filename}"
    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/{filename}_Results.csv", mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Local Frame", "Total Frame", "X", "Y", "Radius", "Video", "Timestamp", "X_init", "Y_init"])
    vid = cv2.VideoCapture(video_file)
    if vid.get(cv2.CAP_PROP_FRAME_COUNT) == 0:
        #print(f"No frames found in {video_file}, skipping.")
        continue
    print(datetime.datetime.now())
    print(f"Starting video {vidnum}: {video_file}")
    frames = extractFrames(vid, filename, totalFrame, totalTime, vidnum)
    totalFrame += frames
    fps = vid.get(cv2.CAP_PROP_FPS)
    frame_count = vid.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps else 0
    delta = datetime.timedelta(seconds=duration)
    totalTime += delta
    vid.release()
print("Processing complete.")

