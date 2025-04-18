# import cv2
# import numpy as np
# import datetime
# import math
# import csv
# import os
# import glob
# import time
# from collections import deque
#
# # Pre-compute morphological kernel
# MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))
#
#
# # Existing utility functions
# def get_mask(frame1, frame2):
#     frame_diff = cv2.subtract(frame2, frame1)
#     frame_diff = cv2.medianBlur(frame_diff, 3)
#     mask = cv2.adaptiveThreshold(
#         frame_diff, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
#         cv2.THRESH_BINARY_INV, 11, 4)
#     mask = cv2.medianBlur(mask, 3)
#     mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, MORPH_KERNEL)
#     _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)
#     return mask
#
#
# def enhance_contrast(gray):
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
#     return clahe.apply(gray)
#
#
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
#
#
# def write(filename, data):
#     out_dir = os.path.join("output", filename)
#     os.makedirs(out_dir, exist_ok=True)
#     with open(os.path.join(out_dir, f"{filename}_Results.csv"), mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(data)
#
#
# # Time tracking utility
# class TimeTracker:
#     def __init__(self, total_frames, report_interval=1000):
#         self.start_time = time.time()
#         self.total_frames = total_frames
#         self.frames_processed = 0
#         self.report_interval = report_interval
#         self.last_report_time = self.start_time
#
#     def update(self, frames=1):
#         self.frames_processed += frames
#         current_time = time.time()
#
#         # Report status at intervals
#         if self.frames_processed % self.report_interval == 0:
#             elapsed_time = current_time - self.start_time
#             time_per_frame = elapsed_time / self.frames_processed if self.frames_processed > 0 else 0
#             remaining_frames = self.total_frames - self.frames_processed
#             remaining_time = remaining_frames * time_per_frame
#
#             progress = (self.frames_processed / self.total_frames) * 100
#
#             print(f"Progress: {self.frames_processed}/{self.total_frames} frames "
#                   f"({progress:.1f}%) - "
#                   f"Elapsed: {self._format_time(elapsed_time)}, "
#                   f"Remaining: {self._format_time(remaining_time)}")
#
#             self.last_report_time = current_time
#
#     def finish(self):
#         total_time = time.time() - self.start_time
#         print(f"Completed in {self._format_time(total_time)}")
#         return total_time
#
#     def _format_time(self, seconds):
#         """Format seconds into a readable time string"""
#         if seconds < 60:
#             return f"{seconds:.1f}s"
#         elif seconds < 3600:
#             minutes = int(seconds // 60)
#             secs = seconds % 60
#             return f"{minutes}m {secs:.1f}s"
#         else:
#             hours = int(seconds // 3600)
#             minutes = int((seconds % 3600) // 60)
#             return f"{hours}h {minutes}m"
#
#
# # PHASE 1: Process downsampled video (30fps)
# def extractFramesDownsampled(video_path, filename,
#                              fps_ratio=4,
#                              target_fps=30,
#                              mask_frac=0.05,
#                              rim_pct=0.20,
#                              block_duration_s=10,
#                              buffer_size=7):
#     """
#     Downsampled pass at `target_fps` to find candidate pulses.
#      - mask_frac: fraction of bell‐area for movement threshold
#      - rim_pct: ±rim_pct * R to define radial band
#      - block_duration_s: seconds per block for amplitude filtering
#      - buffer_size: how many frames to buffer for mask & Hough
#     """
#     out_dir = os.path.join("output", filename)
#     os.makedirs(out_dir, exist_ok=True)
#     csv_path = os.path.join(out_dir, f"{filename}_PotentialPulses.csv")
#     with open(csv_path, 'w', newline='') as f:
#         csv.writer(f).writerow([
#             "DownsampledFrame","OriginalFrameEstimate",
#             "X","Y","Radius","Center_X","Center_Y"
#         ])
#
#     # ensure we have a downsampled file...
#     downpath = os.path.join(out_dir, f"{filename}_downsampled.mp4")
#     if not os.path.exists(downpath):
#         print(f"Creating {target_fps}fps video...")
#         createDownsampledVideo(video_path, downpath, target_fps)
#
#     cap = cv2.VideoCapture(downpath)
#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     tracker = TimeTracker(total_frames)
#
#     # block‐based max area (over block_duration_s)
#     block_length = int(block_duration_s * target_fps)
#     block_max = 0
#     prev_block_max = None
#
#     buf = deque(maxlen=buffer_size)
#     last_gray = None
#     numNotMoving = 0
#     min_sep = int(0.4 * target_fps)
#     candidates = []
#
#     frame_idx = 0
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break
#         tracker.update()
#
#         buf.append(frame.copy())
#         gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
#
#         # wait for buffer fill
#         if last_gray is None or len(buf) < buffer_size:
#             last_gray = gray; frame_idx += 1
#             continue
#
#         # every block_length frames, roll our block maxima
#         if frame_idx % block_length == 0 and frame_idx>0:
#             prev_block_max = block_max
#             block_max = 0
#
#         # compute mask + Hough
#         mask = get_mask(gray, last_gray)
#         center, R = findJellyCircle(buf[-1])
#         area = math.pi * R*R
#
#         # track block max
#         block_max = max(block_max, area)
#
#         # movement threshold
#         if mask.sum() <= mask_frac * area:
#             last_gray = gray; frame_idx +=1
#             numNotMoving +=1
#             continue
#
#         # require some stillness
#         if numNotMoving <= 3:
#             last_gray = gray; frame_idx +=1
#             numNotMoving+=1
#             continue
#
#         # cluster spread
#         pts = np.column_stack(np.where(mask==255))
#         if pts.shape[0]==0 or (pts[:,0].std()+pts[:,1].std())>50:
#             last_gray = gray; frame_idx +=1
#             numNotMoving+=1
#             continue
#
#         # find initiation point
#         medX, medY = pts.mean(axis=0)
#         d2_min = float('inf')
#         init_pt = None
#         for y,x in pts:
#             d2 = (y-medX)**2 + (x-medY)**2
#             if d2<d2_min:
#                 d2_min, init_pt = d2, (y,x)
#
#         # radial band ±rim_pct
#         d2 = (init_pt[0]-center[0])**2 + (init_pt[1]-center[1])**2
#         if not ((1-rim_pct)*R)**2 < d2 < ((1+rim_pct)*R)**2:
#             last_gray = gray; frame_idx +=1
#             numNotMoving+=1
#             continue
#
#         # relative‐amplitude filter
#         if prev_block_max is not None and area < 0.7*prev_block_max:
#             last_gray = gray; frame_idx +=1
#             numNotMoving+=1
#             continue
#
#         # enforce inter‐pulse time
#         if candidates and (frame_idx - candidates[-1][0]) < min_sep:
#             last_gray = gray; frame_idx +=1
#             numNotMoving+=1
#             continue
#
#         # OK — record a candidate
#         orig_est = frame_idx * fps_ratio
#         candidates.append((frame_idx, orig_est, center[0],center[1],R,init_pt[0],init_pt[1]))
#         with open(csv_path, 'a', newline='') as f:
#             csv.writer(f).writerow(candidates[-1])
#         numNotMoving = 0
#
#         last_gray = gray
#         frame_idx +=1
#
#     tracker.finish()
#     cap.release()
#     print(f"Found {len(candidates)} candidates.")
#     return candidates
#
#
#
# def createDownsampledVideo(input_path, output_path, target_fps=30):
#     """
#     Precisely downsample a high‑fps video to `target_fps` by sampling
#     at exact time intervals, avoiding drift.
#     """
#     vid = cv2.VideoCapture(input_path)
#     original_fps = vid.get(cv2.CAP_PROP_FPS)
#     total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
#     width  = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
#
#     # Prepare writer with exact target_fps
#     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
#     out = cv2.VideoWriter(output_path, fourcc, target_fps, (width, height))
#
#     # Number of frames we expect in output
#     out_count = int(round(total_frames * (target_fps/original_fps)))
#
#     tracker = TimeTracker(out_count)
#
#     for i in range(out_count):
#         # compute the exact time (ms) to grab
#         t_ms = (i / target_fps) * 1000
#         vid.set(cv2.CAP_PROP_POS_MSEC, t_ms)
#         ret, frame = vid.read()
#         if not ret:
#             break
#         out.write(frame)
#         tracker.update()
#
#     tracker.finish()
#     vid.release()
#     out.release()
#     print(f"Downsampled to {target_fps}fps, wrote {i+1} frames.")
#     return i+1, original_fps/target_fps
#
#
#
# # PHASE 2: Process selected frames from the original high-fps video
# def processHighResFrames(video_path, filename, potential_pulses, fps_ratio=4, window_size=10):
#     """
#     Process only selected frames from the original high-fps video.
#     Uses the potential_pulses identified in Phase 1.
#     """
#     # Open the original video
#     video = cv2.VideoCapture(video_path)
#     total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
#
#     # Create output directory and initialize results CSV
#     out_dir = os.path.join("output", filename)
#     os.makedirs(out_dir, exist_ok=True)
#
#     with open(os.path.join(out_dir, f"{filename}_Results.csv"), mode='w', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(["Local Frame", "Total Frame", "X", "Y", "Radius",
#                          "Video", "Timestamp", "X_init", "Y_init"])
#
#     # Build set of frames to check
#     frames_to_check = set()
#     for _, original_frame_estimate, *_ in potential_pulses:
#         center_frame = int(original_frame_estimate)
#         for offset in range(-window_size * fps_ratio, window_size * fps_ratio + 1):
#             f = center_frame + offset
#             if 0 <= f < total_frames:
#                 frames_to_check.add(f)
#     frames_to_check = sorted(frames_to_check)
#
#     print(f"Identified {len(potential_pulses)} potential pulses")
#     print(f"Will analyze {len(frames_to_check)} / {total_frames} frames")
#
#     # Initialize trackers & buffers
#     tracker = TimeTracker(len(frames_to_check))
#     currentFrame = 0
#     last_gray = None
#     frame_buffer = deque(maxlen=15)
#
#     # Pulse‐saving variables
#     found = False
#     numSaved = 0       # up to 40
#     movers = []
#     movementCenters = []
#
#     # Carry over your original thresholds and variables
#     numNotMoving = 0
#     block_max_area = 0
#     block_max_data = None
#     previous_block_max_area = None
#     min_separation = 0.4 * video.get(cv2.CAP_PROP_FPS)
#     vidnum = 1
#     totalFrame = 0
#     totalTime = datetime.datetime.now()
#
#     # Process frames
#     while True:
#         ret, cur = video.read()
#         if not ret:
#             break
#
#         if currentFrame not in frames_to_check:
#             currentFrame += 1
#             continue
#
#         tracker.update()
#
#         # Buffer last 15 frames
#         frame_buffer.append(cur.copy())
#         cur_gray = cv2.cvtColor(cur, cv2.COLOR_RGB2GRAY)
#
#         if last_gray is None:
#             last_gray = cur_gray.copy()
#             currentFrame += 1
#             continue
#
#         if len(frame_buffer) >= 15:
#             mask = get_mask(cur_gray, last_gray)
#             jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-1])
#             jelly_area = math.pi * (jellyRadius ** 2)
#
#             # (Your existing block‐based max/threshold logic here...
#             #  compute pulse_threshold_ok, lower_bound, upper_bound, etc.)
#             # threshold adjust
#             # More relaxed bounds to catch all potential pulses
#             pulse_threshold_ok = (previous_block_max_area is None) or (
#                     jelly_area >= 0.9 * previous_block_max_area)
#             lower_bound = (jellyRadius * 0.95) ** 2
#             upper_bound = (jellyRadius * 1.15) ** 2
#             # threshold adjust
#
#             # Suppose pulse_threshold_ok, lower_bound, upper_bound, center_pt are computed:
#             if pulse_threshold_ok and lower_bound < movement_distance_sq < upper_bound and \
#                (len(movers) == 0 or currentFrame - movers[-1] > min_separation):
#
#                 # Write CSV row
#                 delta = datetime.timedelta(seconds=video.get(cv2.CAP_PROP_POS_MSEC) / 1000)
#                 write(filename, [
#                     currentFrame,
#                     totalFrame + currentFrame,
#                     jellyCenter[0],
#                     jellyCenter[1],
#                     jellyRadius,
#                     vidnum,
#                     totalTime + delta,
#                     center_pt[0],
#                     center_pt[1]
#                 ])
#
#                 # Mark pulse for saving
#                 found = True
#                 movers.append(currentFrame)
#                 movementCenters.append(center_pt)
#
#             # === NEW: Pulse‐saving block (up to 40) ===
#             if found and numSaved < 40:
#                 if currentFrame == movers[-1] + 10:
#                     try:
#                         pulse_dir = os.path.join("output", filename, f"pulse{numSaved+1}")
#                         os.makedirs(pulse_dir, exist_ok=True)
#                         center = movementCenters[-1]
#                         buf = list(frame_buffer)
#                         for j in range(1, 16):
#                             img = buf[j-1].copy()
#                             # Draw 7×7 red square
#                             for x in range(center[0]-3, center[0]+4):
#                                 for y in range(center[1]-3, center[1]+4):
#                                     if 0 <= x < img.shape[0] and 0 <= y < img.shape[1]:
#                                         img[x, y] = (0, 0, 255)
#                             cv2.imwrite(os.path.join(pulse_dir, f"frame{j}.jpg"), img)
#                         numSaved += 1
#                     except Exception as e:
#                         print(f"Error saving pulse images: {e}")
#             # === END NEW pulse‐saving ===
#
#         currentFrame += 1
#         last_gray = cur_gray.copy()
#
#     elapsed = tracker.finish()
#     video.release()
#     return currentFrame, elapsed
#
#
#
# # Main execution function
# def main():
#     video_directory = "data/"
#     video_files = glob.glob(os.path.join(video_directory, "*.mp4"))
#     video_files += glob.glob(os.path.join(video_directory, "*.avi"))
#     video_files += glob.glob(os.path.join(video_directory, "*.mov"))
#     video_files += glob.glob(os.path.join(video_directory, "*.mkv"))
#     video_files.sort()
#
#     # Track total processing time
#     total_start_time = time.time()
#     totalFrame = 0
#     totalTime = datetime.datetime.now()
#
#     for vidnum, video_file in enumerate(video_files, start=1):
#         filename = os.path.splitext(os.path.basename(video_file))[0]
#         print(f"\nProcessing video {vidnum}/{len(video_files)}: {filename}")
#
#         # Get original video properties
#         vid = cv2.VideoCapture(video_file)
#         original_fps = vid.get(cv2.CAP_PROP_FPS)
#         total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
#         vid.release()
#
#         # Define target fps for downsampled video (approx 30fps)
#         target_fps = 30
#         fps_ratio = int(round(original_fps / target_fps))
#
#         print(f"Original video: {total_frames} frames at {original_fps}fps")
#         print(f"Using ratio of {fps_ratio}:1 (120fps:30fps)")
#
#         # Phase 1: Process downsampled video to find potential pulses
#         print("\n--- PHASE 1: Processing downsampled video ---")
#         phase1_start = time.time()
#         potential_pulses, phase1_time = extractFramesDownsampled(
#             video_file, filename, fps_ratio, target_fps)
#
#         # Phase 2: Process selected frames from original video
#         print("\n--- PHASE 2: Processing selected frames in high-res video ---")
#         phase2_start = time.time()
#         frames_processed, phase2_time = processHighResFrames(
#             video_file, filename, potential_pulses, fps_ratio) #BUG
#
#         # Calculate time savings
#         total_video_time = phase1_time + phase2_time
#         # Estimate time it would have taken with original approach
#         # based on the ratio of frames processed in Phase 2
#         vid = cv2.VideoCapture(video_file)
#         full_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
#         vid.release()
#
#         # Read the potential pulses from the CSV to get exact count
#         csv_path = os.path.join("output", filename, f"{filename}_PotentialPulses.csv")
#         pulse_count = sum(1 for _ in open(csv_path)) - 1  # subtract header
#
#         # Estimate original approach time - based on phase2 time scaled up
#         frames_to_check = set()
#         for frame_data in potential_pulses:
#             center_frame = int(frame_data[1])  # Original frame estimate
#             window_size = 10
#             for offset in range(-window_size * fps_ratio, window_size * fps_ratio + 1):
#                 frame_to_check = center_frame + offset
#                 if 0 <= frame_to_check < full_frames:
#                     frames_to_check.add(frame_to_check)
#
#         frames_checked = len(frames_to_check)
#         estimated_original_time = (phase2_time / frames_checked) * full_frames if frames_checked > 0 else 0
#
#         # Print performance summary
#         print("\n--- PERFORMANCE SUMMARY ---")
#         print(f"Phase 1 time (30fps): {phase1_time:.2f} seconds")
#         print(f"Phase 2 time (specific 120fps frames): {phase2_time:.2f} seconds")
#         print(f"Total time: {total_video_time:.2f} seconds")
#         print(f"Processed {frames_checked} out of {full_frames} frames in high-res video")
#         print(f"Processing percentage: {(frames_checked / full_frames) * 100:.1f}%")
#         print(f"Estimated time with original approach: {estimated_original_time:.2f} seconds")
#
#         if estimated_original_time > 0:
#             speedup = estimated_original_time / total_video_time
#             print(f"Estimated speedup: {speedup:.1f}x faster")
#             print(f"Time saved: {estimated_original_time - total_video_time:.2f} seconds")
#
#         # Update totals for next video
#         totalFrame += frames_processed
#
#         # Update timestamp
#         fps = vid.get(cv2.CAP_PROP_FPS) if vid else 0
#         frame_count = vid.get(cv2.CAP_PROP_FRAME_COUNT) if vid else 0
#         duration = frame_count / fps if fps else 0
#         totalTime += datetime.timedelta(seconds=duration)
#
#     # Overall timing summary
#     total_time = time.time() - total_start_time
#     print(f"\nOverall processing complete in {total_time:.2f} seconds.")
#
#
# if __name__ == "__main__":
#     main()
#

#NEW CODE WITH PROGRESS BAR
import cv2
import numpy as np
import datetime
import math
import csv
import os
import glob
import time
from collections import deque

# Pre-compute morphological kernel
MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))


# Existing utility functions
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


# Time tracking utility with in-place progress bar
class TimeTracker:
    def __init__(self, total_frames, report_interval=10):
        self.start_time = time.time()
        self.total_frames = total_frames
        self.frames_processed = 0
        self.report_interval = report_interval
        self.last_report_time = self.start_time
        self.bar_width = 40  # Width of progress bar

    def update(self, frames=1):
        self.frames_processed += frames
        current_time = time.time()

        # Report status at intervals
        if self.frames_processed % self.report_interval == 0 or self.frames_processed == self.total_frames:
            elapsed_time = current_time - self.start_time
            time_per_frame = elapsed_time / self.frames_processed if self.frames_processed > 0 else 0
            remaining_frames = self.total_frames - self.frames_processed
            remaining_time = remaining_frames * time_per_frame

            progress = min(1.0, self.frames_processed / self.total_frames)

            # Create progress bar
            filled_len = int(self.bar_width * progress)
            bar = '█' * filled_len + '░' * (self.bar_width - filled_len)

            # Clear line and print progress bar (stays on same line)
            print(f"\r|{bar}| {progress * 100:.1f}% ({self.frames_processed}/{self.total_frames}) - "
                  f"Elapsed: {self._format_time(elapsed_time)} - "
                  f"ETA: {self._format_time(remaining_time)}", end="", flush=True)

            self.last_report_time = current_time

    def finish(self):
        total_time = time.time() - self.start_time
        # Print a newline after finishing to allow next output to start on new line
        print(f"\nCompleted in {self._format_time(total_time)}")
        return total_time

    def _format_time(self, seconds):
        """Format seconds into a readable time string"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


# PHASE 1: Process downsampled video (15fps)
def extractFramesDownsampled(video_path, filename, fps_ratio=8, target_fps=15):
    """
    Process downsampled video to identify potential pulse frames.
    Returns a list of potential pulse frame data.
    """
    # Create output directory
    out_dir = os.path.join("output", filename)
    os.makedirs(out_dir, exist_ok=True)

    # Create CSV for potential pulses
    csv_path = os.path.join(out_dir, f"{filename}_PotentialPulses.csv")
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Downsampled Frame", "Original Frame Estimate",
                         "X", "Y", "Radius", "Center_X", "Center_Y"])

    # Create downsampled video if it doesn't exist
    downsampled_path = os.path.join(out_dir, f"{filename}_downsampled.mp4")
    if not os.path.exists(downsampled_path):
        print(f"\nCreating downsampled video at {target_fps}fps...")
        # Only get the skip_rate from createDownsampledVideo to fix the unpacking error
        fps_ratio = createDownsampledVideo(video_path, downsampled_path, target_fps)

    # Process the downsampled video
    print(f"\nProcessing downsampled video ({target_fps}fps)...")
    video = cv2.VideoCapture(downsampled_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    # Initialize time tracker
    tracker = TimeTracker(total_frames)

    # Processing variables
    currentFrame = 0
    numNotMoving = 0
    frame_buffer = deque(maxlen=15)
    last_gray = None
    potential_pulses = []
    min_separation = 0.4 * target_fps  # Adjust for downsampled fps

    while True:
        ret, cur = video.read()
        if not ret:
            break

        # Update progress
        tracker.update()

        # Store frame in buffer
        frame_buffer.append(cur.copy())
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_RGB2GRAY)

        if last_gray is None:
            last_gray = cur_gray.copy()
            currentFrame += 1
            continue

        if len(frame_buffer) < 15:
            currentFrame += 1
            last_gray = cur_gray.copy()
            continue

        # Detect movement
        mask = get_mask(cur_gray, last_gray)
        jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-1])
        jelly_area = math.pi * (jellyRadius ** 2)

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

                    # Use slightly more lenient criteria for the first pass
                    jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-4])
                    jellyRadius = int(jellyRadius)
                    dvert = int(jellyCenter[0] - center_pt[0])
                    dhor = int(center_pt[1] - jellyCenter[1])
                    movement_distance_sq = dhor ** 2 + dvert ** 2

                    # More relaxed bounds to catch all potential pulses
                    lower_bound = (jellyRadius * 0.5) ** 2
                    upper_bound = (jellyRadius * 1.5) ** 2

                    if lower_bound < movement_distance_sq < upper_bound and \
                            (len(potential_pulses) == 0 or
                             currentFrame - potential_pulses[-1][0] > min_separation):

                        # Estimate original frame number
                        original_frame_estimate = currentFrame * fps_ratio

                        # Store the potential pulse
                        pulse_data = (currentFrame, original_frame_estimate,
                                      jellyCenter[0], jellyCenter[1],
                                      jellyRadius, center_pt[0], center_pt[1])
                        potential_pulses.append(pulse_data)

                        # Write to CSV
                        with open(csv_path, mode='a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(pulse_data)

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
        last_gray = cur_gray.copy()

    # Finish and report
    elapsed_time = tracker.finish()
    print(f"Found {len(potential_pulses)} potential pulses in downsampled video.")

    video.release()
    # Return only the potential_pulses to fix the unpacking issue
    return potential_pulses


def createDownsampledVideo(input_path, output_path, target_fps=15):
    """Create a downsampled version of the video at the specified target FPS"""
    vid = cv2.VideoCapture(input_path)
    original_fps = vid.get(cv2.CAP_PROP_FPS)

    # Skip rate to achieve target fps
    skip_rate = int(round(original_fps / target_fps))

    # Get video properties
    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, target_fps, (width, height))

    # Track progress
    tracker = TimeTracker(total_frames // skip_rate)

    frame_idx = 0
    frames_written = 0

    while True:
        ret, frame = vid.read()
        if not ret:
            break

        # Only keep frames at the target rate
        if frame_idx % skip_rate == 0:
            out.write(frame)
            frames_written += 1
            tracker.update()

        frame_idx += 1

    # Finish
    elapsed_time = tracker.finish()
    print(f"Created downsampled video with {frames_written} frames at {target_fps}fps")

    vid.release()
    out.release()
    # Only return the skip_rate to fix the unpacking error
    return skip_rate


# PHASE 2: Process selected frames from the original high-fps video
def processHighResFrames(video_path, filename, potential_pulses, fps_ratio=8, window_size=10):
    """
    Process only selected frames from the original high-fps video.
    Uses the potential_pulses identified in Phase 1.
    """
    # Open the original video
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    # Create output directory and initialize results CSV
    out_dir = os.path.join("output", filename)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, f"{filename}_Results.csv"), mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Local Frame", "Total Frame", "X", "Y", "Radius",
                         "Video", "Timestamp", "X_init", "Y_init"])

    # Determine which frames to process
    frames_to_check = set()
    for _, original_frame_estimate, *_ in potential_pulses:
        center_frame = int(original_frame_estimate)
        # Add window of frames around each potential pulse
        for offset in range(-window_size * fps_ratio, window_size * fps_ratio + 1):
            frame_to_check = center_frame + offset
            if 0 <= frame_to_check < total_frames:
                frames_to_check.add(frame_to_check)

    frames_to_check = sorted(list(frames_to_check))

    print(f"Identified {len(potential_pulses)} potential pulses")
    print(f"Will analyze {len(frames_to_check)} out of {total_frames} frames "
          f"({len(frames_to_check) / total_frames * 100:.1f}% of original)")

    # Initialize processing variables
    tracker = TimeTracker(len(frames_to_check))
    currentFrame = 0
    numNotMoving = 0  # Added missing variable
    last_gray = None
    frame_buffer = deque(maxlen=15)
    movers = []
    movementCenters = []
    found = False  # Added missing variable

    # Variables from original code
    block_max_area = 0
    block_max_data = None
    previous_block_max_area = None
    min_separation = 0.4 * video.get(cv2.CAP_PROP_FPS)  # use original fps
    user_input = video.get(cv2.CAP_PROP_FPS)  # default to video fps
    vidnum = 1
    totalFrame = 0
    totalTime = datetime.datetime.now()

    # Process frames
    while True:
        ret, cur = video.read()
        if not ret:
            break

        # Skip frames that aren't in our list to check
        if currentFrame not in frames_to_check:
            currentFrame += 1
            continue

        # Update progress
        tracker.update()

        # Process this frame (using logic from original code)
        frame_buffer.append(cur.copy())
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_RGB2GRAY)

        if last_gray is None:
            last_gray = cur_gray.copy()
            currentFrame += 1
            continue

        # Now process using full criteria from original code
        if len(frame_buffer) >= 15:
            mask = get_mask(cur_gray, last_gray)
            jellyCenter, jellyRadius = findJellyCircle(frame_buffer[-1])
            jelly_area = math.pi * (jellyRadius ** 2)

            # Block processing logic from original code
            if jelly_area > block_max_area:
                block_max_area = jelly_area
                block_max_data = (cur_gray.copy(), jellyCenter, jellyRadius, currentFrame)

            if currentFrame % 72000 == 0:
                if currentFrame != 0:
                    previous_block_max_area = block_max_area
                    print(f"\nBlock ending at frame {currentFrame - 1}: block_max_area = {previous_block_max_area:.2f}")
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

                        # Use a slightly earlier frame from the buffer
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
        last_gray = cur_gray.copy()

    # Finish and report
    tracker.finish()
    video.release()

    # Only return the processed frames count to fix unpacking error
    return currentFrame


# Main execution function
def main():
    video_directory = "data/"
    video_files = glob.glob(os.path.join(video_directory, "*.mp4"))
    video_files += glob.glob(os.path.join(video_directory, "*.avi"))
    video_files += glob.glob(os.path.join(video_directory, "*.mov"))
    video_files += glob.glob(os.path.join(video_directory, "*.mkv"))
    video_files.sort()

    # Get user input for fps
    user_input = input("Please enter fps of the video: ")
    print("You entered:", user_input)
    user_input = float(user_input)

    # Track total processing time
    total_start_time = time.time()
    totalFrame = 0
    totalTime = datetime.datetime.now()

    for vidnum, video_file in enumerate(video_files, start=1):
        filename = os.path.splitext(os.path.basename(video_file))[0]
        print(f"\nProcessing video {vidnum}/{len(video_files)}: {filename}")

        # Get original video properties
        vid = cv2.VideoCapture(video_file)
        original_fps = vid.get(cv2.CAP_PROP_FPS)
        total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
        vid.release()

        # Define target fps for downsampled video (approx 15fps)
        target_fps = 15
        fps_ratio = int(round(original_fps / target_fps))

        print(f"Original video: {total_frames} frames at {original_fps}fps")
        print(f"Using ratio of {fps_ratio}:1 ({original_fps}fps:{target_fps}fps)")

        # Phase 1: Process downsampled video to find potential pulses
        print("\n--- PHASE 1: Processing downsampled video ---")
        phase1_start = time.time()
        # Fix: Only expect one return value from extractFramesDownsampled
        potential_pulses = extractFramesDownsampled(
            video_file, filename, fps_ratio, target_fps)
        phase1_time = time.time() - phase1_start

        # Phase 2: Process selected frames from original video
        print("\n--- PHASE 2: Processing selected frames in high-res video ---")
        phase2_start = time.time()
        # Fix: Only expect one return value from processHighResFrames
        frames_processed = processHighResFrames(
            video_file, filename, potential_pulses, fps_ratio)
        phase2_time = time.time() - phase2_start

        # Calculate time savings
        total_video_time = phase1_time + phase2_time

        # Estimate time it would have taken with original approach
        vid = cv2.VideoCapture(video_file)
        full_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
        vid.release()

        # Read the potential pulses from the CSV to get exact count
        csv_path = os.path.join("output", filename, f"{filename}_PotentialPulses.csv")
        # Check if file exists before counting
        if os.path.exists(csv_path):
            pulse_count = sum(1 for _ in open(csv_path)) - 1  # subtract header
        else:
            pulse_count = 0

        # Estimate original approach time - based on phase2 time scaled up
        frames_to_check = set()
        for frame_data in potential_pulses:
            center_frame = int(frame_data[1])  # Original frame estimate
            window_size = 10
            for offset in range(-window_size * fps_ratio, window_size * fps_ratio + 1):
                frame_to_check = center_frame + offset
                if 0 <= frame_to_check < full_frames:
                    frames_to_check.add(frame_to_check)

        frames_checked = len(frames_to_check)
        estimated_original_time = (phase2_time / frames_checked) * full_frames if frames_checked > 0 else 0

        # Print performance summary
        print("\n--- PERFORMANCE SUMMARY ---")
        print(f"Phase 1 time (15fps): {phase1_time:.2f} seconds")
        print(f"Phase 2 time (specific 120fps frames): {phase2_time:.2f} seconds")
        print(f"Total time: {total_video_time:.2f} seconds")
        print(f"Processed {frames_checked} out of {full_frames} frames in high-res video")
        print(f"Processing percentage: {(frames_checked / full_frames) * 100:.1f}%")
        print(f"Estimated time with original approach: {estimated_original_time:.2f} seconds")

        if estimated_original_time > 0:
            speedup = estimated_original_time / total_video_time
            print(f"Estimated speedup: {speedup:.1f}x faster")
            print(f"Time saved: {estimated_original_time - total_video_time:.2f} seconds")

        # Update totals for next video
        totalFrame += frames_processed

        # Update timestamp
        fps = original_fps  # Use the original_fps we already determined
        duration = full_frames / fps if fps else 0
        totalTime += datetime.timedelta(seconds=duration)

    # Overall timing summary
    total_time = time.time() - total_start_time
    print(f"\nOverall processing complete in {total_time:.2f} seconds.")


if __name__ == "__main__":
    main()