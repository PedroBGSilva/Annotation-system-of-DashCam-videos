import cv2
from shapely.geometry import Polygon, LineString, Point
import numpy as np
import matplotlib.pyplot as plt


class IntersectionOverUnionTracker:
    def __init__(self):
        # Store the bounding box points from the cars
        self.bb_points = {}
        self.bb_sizes = {}
        # Keep the count of the IDs
        # each time a new car is detected, the count will increase by one
        self.id_count = 0
        self.id_count_check = 0

    def __add_car(self, vehicle, bbs_ids, check_only=False):
        car = Polygon(vehicle)
        car = car.buffer(0)

        for car_id, car_points in self.bb_points.items():
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
                    self.bb_points[car_id] = vehicle
                    bbs_ids.append([vehicle, car_id])
                    return bbs_ids

        # If the car does not exist, assign new ID to the car
        if check_only:
            return self.id_count
        else:
            self.bb_points[self.id_count] = vehicle
            bbs_ids.append([vehicle, self.id_count])
            self.id_count += 1
            return bbs_ids

    def update(self, image, detected_cars, curr_frame_idx, line_thickness=3, plot_cars=True):
        if len(detected_cars) > 0:
            # Cars bbs and IDs
            car_bbs_ids = []

            # Get points of each detected car
            for curr_car in detected_cars:
                # Find out if the car already exists
                car_bbs_ids = self.__add_car(curr_car, car_bbs_ids)

            # Clean the dictionary by removing IDs not used anymore
            new_bb_points = {}
            for vertices, id in car_bbs_ids:
                points = self.bb_points[id]
                new_bb_points[id] = points

            # Update dictionary with non used IDs removed
            self.bb_points = new_bb_points.copy()

            if plot_cars:
                self.__plot_car_ids(image, line_thickness)

            self.__save_bb_size(curr_frame_idx)

    def __save_bb_size(self, curr_frame_idx):
        # Fill the bounding box sizes list of the non present cars with None or the bb area for existing cars
        if len(self.bb_sizes) > 0:
            # Get the IDs of the new cars in the present frame
            new_car_ids = list(set(self.bb_points.keys()) - set(self.bb_sizes.keys()))
            # Fill the lists with the bb area or None, when the car is no longer present in the frame
            for car_id, bb_size in self.bb_sizes.items():
                car_area = None
                if car_id in self.bb_points.keys():
                    car_bb = self.bb_points[car_id]
                    car_area = Polygon(car_bb).area
                bb_size.append(car_area)

            # Add to the bb sizes dictionary the new cars present in the current frame
            for car_id in new_car_ids:
                car_bb = self.bb_points[car_id]
                car_area = Polygon(car_bb).area
                bb_size = [None] * (curr_frame_idx - 1)
                bb_size.append(car_area)
                self.bb_sizes[car_id] = bb_size

        # In case there are still no car bb sizes added to the dictionary
        else:
            for car_id, bb in self.bb_points.items():
                car_area = Polygon(bb).area
                bb_size = [None] * (curr_frame_idx - 1)
                bb_size.append(car_area)
                self.bb_sizes[car_id] = bb_size

    def get_bb_area_variance(self, car_id, save_dir):
        if car_id in self.bb_sizes.keys():
            bb_values = self.bb_sizes[car_id]
            i = 0
            x = list()
            y = list()
            for bb_value in bb_values:
                if bb_value is not None:
                    x.append(i)
                    y.append(bb_value)
                i += 1
            plt.plot(x, y)
            plt.savefig(f"{save_dir}/Area car {car_id}.png")
            plt.clf()
            slope = np.gradient(y)
            plt.plot(x, slope)
            plt.savefig(f"{save_dir}/Slope car {car_id}.png")
            plt.clf()

    def get_distance_in_frame(self, id, video_lanes):
        if id not in self.bb_points.keys():
            return None
        rect_car = self.bb_points[id]
        car = Polygon(rect_car)
        cx_car = (rect_car[0][0] + rect_car[1][0]) // 2
        cy_car = (rect_car[0][1] + rect_car[1][1]) // 2
        c_car = Point(cx_car, cy_car)
        rect_lane = video_lanes[-1]
        lane_points = [[(rect_lane[0][0] + rect_lane[1][0]) // 2, (rect_lane[0][1] + rect_lane[1][1]) // 2],
                       [(rect_lane[0][2] + rect_lane[1][2]) // 2, (rect_lane[0][3] + rect_lane[1][3]) // 2]]
        lane = LineString(lane_points)
        return c_car.distance(lane) / car.area

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
        if len(self.bb_points) > 0:
            tl = line_thickness or round(0.002 * (image.shape[0] + image.shape[1]) / 2) + 1  # line/font thickness
            tf = max(tl - 1, 1)  # font thickness

            for car_id, car_points in self.bb_points.items():
                label_car_id = "" + str(car_id)
                font_size = cv2.getTextSize(label_car_id, 0, fontScale=tl / 3, thickness=tf)[0]  # line/font thickness

                p_text = (car_points[0][0], car_points[0][1] - 2)
                p1 = (car_points[0][0], car_points[0][1])
                p2 = (car_points[0][0] + font_size[0], car_points[0][1] - font_size[1] - 3)

                cv2.rectangle(image, p1, p2, [74, 207, 237], -1, cv2.LINE_AA)
                cv2.putText(image, label_car_id, p_text, 0, tl / 3, [0, 0, 0], thickness=tf, lineType=cv2.LINE_AA)