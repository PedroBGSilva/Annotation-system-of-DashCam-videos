import cv2
from shapely.geometry import Polygon, LineString, Point
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import lfilter
import csv

width = 768


class IntersectionOverUnionTracker:
    def __init__(self):
        # Store the bounding boxes' features
        self.__bb_points_all = {}
        self.__bb_points, self.__bb_points_last, self.__bb_points_old, self.__bb_points_older, self.__bb_points_oldest = {}, {}, {}, {}, {}
        self.__bb_areas, self.__bb_distances, self.__bb_intersections, self.__bb_area_variance, self.__bb_distance_variance = {}, {}, {}, {}, {}
        # Keep the count of the IDs each time a new car is detected, the count will increase by one
        self.__id_count, self.__id_count_check = 0, 0
        # Annotations
        self.__annotations_video = list()

    def __add_car(self, vehicle, bbs_ids, check_only=False):
        car = Polygon(vehicle)
        car = car.buffer(0)

        all_bb_points = self.__bb_points_oldest.copy()
        all_bb_points.update(self.__bb_points_older)
        all_bb_points.update(self.__bb_points_old)
        all_bb_points.update(self.__bb_points_last)
        all_bb_points.update(self.__bb_points)

        for car_id, car_points in all_bb_points.items():
            existent_car = Polygon(car_points)
            existent_car = existent_car.buffer(0)
            intersection = car.intersection(existent_car)
            union = car.union(existent_car)
            iou = round(((intersection.area / union.area) * 100), 2)

            # If car exists already, update correspondent ID bounding box points
            if iou > 40.00:
                if check_only:
                    return car_id
                else:
                    self.__bb_points[car_id] = vehicle
                    bbs_ids.append([vehicle, car_id])
                    return bbs_ids

        # If the car does not exist, assign new ID to the car
        if check_only:
            return self.__id_count
        else:
            self.__bb_points[self.__id_count] = vehicle
            bbs_ids.append([vehicle, self.__id_count])
            self.__id_count += 1
            return bbs_ids

    def update(self, image, curr_frame_idx, detected_cars, video_lanes, line_thickness=3, plot_cars=True):
        if len(detected_cars) > 0:
            # Cars bbs and IDs
            car_bbs_ids = []

            # Get points of each detected car
            for curr_car in detected_cars:
                # Find out if the car already exists
                car_bbs_ids = self.__add_car(curr_car, car_bbs_ids)

            # Clean the dictionary by removing IDs not used anymore
            new_bb_points = {}
            for vertices, car_id in car_bbs_ids:
                points = self.__bb_points[car_id]
                new_bb_points[car_id] = points

            # Save the last 4 dictionaries
            self.__bb_points_oldest = self.__bb_points_older
            self.__bb_points_older = self.__bb_points_old
            self.__bb_points_old = self.__bb_points_last
            self.__bb_points_last = self.__bb_points
            # Update dictionary with non used IDs removed
            self.__bb_points = new_bb_points.copy()

            if plot_cars:
                self.__plot_car_ids(image, line_thickness)

            self.__save_bb_features(curr_frame_idx, video_lanes)

    def __save_bb_features(self, curr_frame_idx, video_lanes):
        # Fill the bounding box sizes list of the non present cars with None or the bb area for existing cars
        if len(self.__bb_areas) > 0:
            # Get the IDs of the new cars in the present frame
            new_car_ids = list(set(self.__bb_points.keys()) - set(self.__bb_areas.keys()))
            # Fill the lists with the bb area or None, when the car is no longer present in the frame
            for car_id in self.__bb_areas.keys():
                car, car_area, car_distance, car_intersection = None, None, None, None
                if car_id in self.__bb_points.keys():
                    car = self.__bb_points[car_id]
                    car_bb = Polygon(car)
                    car_area = car_bb.area
                    car_distance = get_distance_in_frame(car, car_area, video_lanes)
                    car_intersection = get_intersection_value(car, video_lanes)
                self.__bb_points_all[car_id].append(car)
                self.__bb_areas[car_id].append(car_area)
                self.__bb_distances[car_id].append(car_distance)
                self.__bb_intersections[car_id].append(car_intersection)

            # Add to the bb sizes dictionary the new cars present in the current frame
            for car_id in new_car_ids:
                car = self.__bb_points[car_id]
                car_bb = Polygon(car)

                bb = [None] * (curr_frame_idx - 1)
                bb.append(car)
                self.__bb_points_all[car_id] = bb

                car_area = car_bb.area
                bb_size = [None] * (curr_frame_idx - 1)
                bb_size.append(car_area)
                self.__bb_areas[car_id] = bb_size

                car_distance = get_distance_in_frame(car, car_area, video_lanes)
                bb_distance = [None] * (curr_frame_idx - 1)
                bb_distance.append(car_distance)
                self.__bb_distances[car_id] = bb_distance

                car_intersection = get_intersection_value(car, video_lanes)
                bb_intersection = [None] * (curr_frame_idx - 1)
                bb_intersection.append(car_intersection)
                self.__bb_intersections[car_id] = bb_intersection

        # In case there are still no car bb sizes added to the dictionary
        else:
            for car_id in self.__bb_points.keys():
                car = self.__bb_points[car_id]
                car_bb = Polygon(car)

                bb = [None] * (curr_frame_idx - 1)
                bb.append(car)
                self.__bb_points_all[car_id] = bb

                car_area = car_bb.area
                bb_size = [None] * (curr_frame_idx - 1)
                bb_size.append(car_area)
                self.__bb_areas[car_id] = bb_size

                car_distance = get_distance_in_frame(car, car_area, video_lanes)
                bb_distance = [None] * (curr_frame_idx - 1)
                bb_distance.append(car_distance)
                self.__bb_distances[car_id] = bb_distance

                car_intersection = get_intersection_value(car, video_lanes)
                bb_intersection = [None] * (curr_frame_idx - 1)
                bb_intersection.append(car_intersection)
                self.__bb_intersections[car_id] = bb_intersection

    def get_features_variance(self):
        for car_id in self.__bb_areas.keys():
            bb_area_values = self.__bb_areas[car_id]
            bb_distance_values = self.__bb_distances[car_id]

            i, x, y_area, y_distance = 0, list(), list(), list()
            for bb_distance_value in bb_distance_values:
                if bb_distance_value is not None:
                    x.append(i)
                    y_area.append(bb_area_values[i])
                    y_distance.append(bb_distance_value)
                i += 1

            if len(x) > 1:
                n = 50  # the larger n is, the smoother curve will be
                b = [1.0 / n] * n
                yy_area = lfilter(b, 1, np.gradient(y_area) / y_area)
                yy_distance = lfilter(b, 1, np.gradient(y_distance))

                bb_area_variance_values = bb_area_values.copy()
                bb_distance_variance_values = bb_distance_values.copy()

                i1, i2 = 0, 0
                for bb_distance_value in bb_distance_values:
                    if bb_distance_value is not None:
                        bb_area_variance_values[i2] = yy_area[i1]
                        bb_distance_variance_values[i2] = yy_distance[i1]
                        i1 += 1
                    i2 += 1

                self.__bb_area_variance[car_id] = bb_area_variance_values
                self.__bb_distance_variance[car_id] = bb_distance_variance_values

    def plot_features(self, save_dir, plot_car_id):
        if plot_car_id is not None and plot_car_id in self.__bb_areas.keys():
            bb_area_values = self.__bb_areas[plot_car_id]
            bb_distance_values = self.__bb_distances[plot_car_id]
            bb_intersection_values = self.__bb_intersections[plot_car_id]
            bb_area_variance_values = self.__bb_area_variance[plot_car_id]
            bb_distance_variance_values = self.__bb_distance_variance[plot_car_id]

            i, x, y_area, y_distance, y_intersection, yy_area, yy_distance = 0, list(), list(), list(), list(), list(), list()
            for bb_value in bb_area_values:
                if bb_value is not None:
                    x.append(i)
                    y_area.append(bb_value)
                    y_distance.append(bb_distance_values[i])
                    y_intersection.append(bb_intersection_values[i])
                    yy_area.append(bb_area_variance_values[i])
                    yy_distance.append(bb_distance_variance_values[i])
                i += 1

            plt.plot(x, y_area)
            plt.savefig(f"{save_dir}/Area car {plot_car_id}.png")
            plt.clf()

            plt.plot(x, y_distance)
            plt.savefig(f"{save_dir}/Distance car {plot_car_id}.png")
            plt.clf()

            plt.plot(x, y_intersection)
            plt.savefig(f"{save_dir}/Intersection car {plot_car_id}.png")
            plt.clf()

            if yy_area:
                plt.plot(x, yy_area)
                plt.savefig(f"{save_dir}/Area derivative car {plot_car_id}.png")
                plt.clf()

            if yy_distance:
                plt.plot(x, yy_distance)
                plt.savefig(f"{save_dir}/Distance derivative car {plot_car_id}.png")
                plt.clf()

    def get_vehicle_label_points(self, vehicle, image, line_thickness=3):
        car_id = self.__add_car(vehicle, None, check_only=True)
        tl = line_thickness or round(0.002 * (image.shape[0] + image.shape[1]) / 2) + 1  # line/font thickness
        tf = max(tl - 1, 1)  # font thickness
        label = "" + str(car_id) + "0"
        font_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]  # line/font thickness
        car_label_coords = (vehicle[0][0] + font_size[0] + 1, vehicle[0][1] - 2)
        car_label_rect_coords = [(vehicle[0][0] + font_size[0], vehicle[0][1]),
                                 (vehicle[0][0] + font_size[0] + 1, vehicle[0][1] - font_size[1] - 3)]

        return car_label_coords, car_label_rect_coords

    def __plot_car_ids(self, image, line_thickness):
        if len(self.__bb_points) > 0:
            tl = line_thickness or round(0.002 * (image.shape[0] + image.shape[1]) / 2) + 1  # line/font thickness
            tf = max(tl - 1, 1)  # font thickness

            for car_id, car_points in self.__bb_points.items():
                label_car_id = "" + str(car_id)
                font_size = cv2.getTextSize(label_car_id, 0, fontScale=tl / 3, thickness=tf)[0]  # line/font thickness

                p_text = (car_points[0][0], car_points[0][1] - 2)
                p1 = (car_points[0][0], car_points[0][1])
                p2 = (car_points[0][0] + font_size[0], car_points[0][1] - font_size[1] - 3)

                cv2.rectangle(image, p1, p2, [74, 207, 237], -1, cv2.LINE_AA)
                cv2.putText(image, label_car_id, p_text, 0, tl / 3, [0, 0, 0], thickness=tf, lineType=cv2.LINE_AA)

    def analyze_features(self, save_dir):
        with open(f"{save_dir}/annotations.csv", 'w', newline='') as annotations:
            fieldnames = ['frame', 'danger', 'danger_front', 'danger_left', 'danger_right', 'lane_entry', 'entry_left', 'entry_right',
                          'lane_departure', 'departure_left', 'departure_right', 'approx', 'approx_front', 'approx_left', 'approx_right',
                          'total_cars', 'car_in_lane', 'cars_on_left', 'cars_on_right']
            writer = csv.DictWriter(annotations, fieldnames=fieldnames)
            writer.writeheader()
            if len(self.__bb_areas[0]) > 0:
                for frame in range(len(self.__bb_areas[0])):
                    danger, danger_front, danger_left, danger_right = False, False, False, False
                    lane_entry, entry_left, entry_right = False, False, False
                    lane_departure, departure_left, departure_right = False, False, False
                    approx, approx_front, approx_left, approx_right = False, False, False, False
                    total_cars, car_in_lane, cars_on_left, cars_on_right = 0, False, 0, 0
                    x = 4
                    if frame < x:
                        x = frame
                    for car_id in self.__bb_area_variance.keys():
                        # Last 5 frames variance values
                        a = [z for z in self.__bb_area_variance[car_id][frame - x:frame + 1] if z is not None]
                        d = [z for z in self.__bb_distance_variance[car_id][frame - x:frame + 1] if z is not None]
                        # Car points and intersection value for actual frame
                        actual_i = self.__bb_intersections[car_id][frame]
                        actual_car = self.__bb_points_all[car_id][frame]
                        # Car points and intersection value for the last frame
                        last_i = self.__bb_intersections[car_id][frame]
                        last_car = self.__bb_points_all[car_id][frame]
                        if a and d and actual_i is not None:
                            if actual_i >= 50:
                                car_in_lane = True
                                if last_i is not None:
                                    if last_i < 50:
                                        lane_entry = True
                                        if last_car is not None:
                                            cx_car = (last_car[0][0] + last_car[1][0]) // 2
                                            if cx_car < width // 2:
                                                entry_left = True
                                            else:
                                                entry_right = True
                                if np.mean(a) > 0:
                                    approx = True
                                    approx_front = True
                                    if np.mean(a) > 0.05:
                                        danger_front = True
                                        danger = True
                            else:
                                cx_car = (actual_car[0][0] + actual_car[1][0]) // 2
                                if last_i is not None:
                                    if last_i >= 50:
                                        lane_departure = True
                                        if actual_car is not None:
                                            if cx_car < width // 2:
                                                departure_left = True
                                            else:
                                                departure_right = True
                                    if cx_car < width // 2:
                                        cars_on_left += 1
                                        if np.mean(d) < 0:
                                            approx = True
                                            approx_left = True
                                            if actual_i > 0 and np.mean(a) >= 0:
                                                danger = True
                                                danger_left = True
                                    else:
                                        cars_on_right += 1
                                        if np.mean(d) < 0:
                                            approx = True
                                            approx_right = True
                                            if actual_i > 0 and np.mean(a) >= 0:
                                                danger = True
                                                danger_right = True
                    total_cars = car_in_lane + cars_on_left + cars_on_right
                    writer.writerow({'frame': frame, 'danger': danger, 'danger_front': danger_front, 'danger_left': danger_left,
                                     'danger_right': danger_right, 'lane_entry': lane_entry, 'entry_left': entry_left,
                                     'entry_right': entry_right, 'lane_departure': lane_departure, 'departure_left': departure_left,
                                     'departure_right': departure_right, 'approx': approx, 'approx_front': approx_front,
                                     'approx_left': approx_left, 'approx_right': approx_right, 'total_cars': total_cars,
                                     'car_in_lane': car_in_lane, 'cars_on_left': cars_on_left, 'cars_on_right': cars_on_right})


def get_intersection_value(car, video_lanes):
    if len(video_lanes) > 0:
        lane_vertices = np.array([[video_lanes[-1][0][0], video_lanes[-1][0][1]], [video_lanes[-1][0][2], video_lanes[-1][0][3]],
                                  [video_lanes[-1][1][2], video_lanes[-1][1][3]], [video_lanes[-1][1][0], video_lanes[-1][1][1]]])
        lane_bb = Polygon(np.reshape(lane_vertices, (4, 2))).buffer(0)
        car_bb = Polygon(car).buffer(0)
        percentage = 0
        if lane_bb.intersects(car_bb):
            intersection = car_bb.intersection(lane_bb).area
            percentage = (intersection / car_bb.area) * 100

        return percentage
    return None


def get_distance_in_frame(car, car_area, video_lanes):
    if len(video_lanes) > 0:
        cx_car = (car[0][0] + car[1][0]) // 2
        cy_car = (car[0][1] + car[1][1]) // 2
        c_car = Point(cx_car, cy_car)
        rect_lane = video_lanes[-1]
        lane_points = [[(rect_lane[0][0] + rect_lane[1][0]) // 2, (rect_lane[0][1] + rect_lane[1][1]) // 2],
                       [(rect_lane[0][2] + rect_lane[1][2]) // 2, (rect_lane[0][3] + rect_lane[1][3]) // 2]]
        lane = LineString(lane_points)
        distance_in_pixels = (c_car.distance(lane) * c_car.distance(lane)) / car_area
        # one_and_half_meter = lane_points[0][0] - rect_lane[0][0]
        # distance_in_meters = (distance_in_pixels * 1.5) / one_and_half_meter

        return distance_in_pixels
    return None
