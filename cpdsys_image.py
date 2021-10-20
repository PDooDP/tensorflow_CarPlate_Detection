# ==============================================
# Credit: Nicholas Renotte (YouTube Channel)
# Dataset source: Car Plates Detection from Kaggle
# ==============================================
# Using Single Shot Detection (SSD) and EasyOCR
# Initial setup
import os
import tensorflow as tf
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as viz_utils
from object_detection.builders import model_builder
from object_detection.utils import config_util

# opencv
import cv2 
import numpy as np
# from matplotlib import pyplot as plt
import matplotlib.pyplot as plt
import easyocr

# saving results into csv
import csv
import uuid

# Initial Settings
CUSTOM_MODEL_NAME = 'my_ssd_mobnet' 
PRETRAINED_MODEL_NAME = 'ssd_mobilenet_v2_fpnlite_320x320_coco17_tpu-8'
PRETRAINED_MODEL_URL = 'http://download.tensorflow.org/models/object_detection/tf2/20200711/ssd_mobilenet_v2_fpnlite_320x320_coco17_tpu-8.tar.gz'
TF_RECORD_SCRIPT_NAME = 'generate_tfrecord.py'
LABEL_MAP_NAME = 'label_map.pbtxt'

paths = {
    'WORKSPACE_PATH': os.path.join('Tensorflow', 'workspace'),
    'SCRIPTS_PATH': os.path.join('Tensorflow','scripts'),
    'APIMODEL_PATH': os.path.join('Tensorflow','models'),
    'ANNOTATION_PATH': os.path.join('Tensorflow', 'workspace','annotations'),
    'IMAGE_PATH': os.path.join('Tensorflow', 'workspace','images'),
    'MODEL_PATH': os.path.join('Tensorflow', 'workspace','models'),
    'PRETRAINED_MODEL_PATH': os.path.join('Tensorflow', 'workspace','pre-trained-models'),
    'CHECKPOINT_PATH': os.path.join('Tensorflow', 'workspace','models',CUSTOM_MODEL_NAME), 
    'OUTPUT_PATH': os.path.join('Tensorflow', 'workspace','models',CUSTOM_MODEL_NAME, 'export'), 
    'TFJS_PATH':os.path.join('Tensorflow', 'workspace','models',CUSTOM_MODEL_NAME, 'tfjsexport'), 
    'TFLITE_PATH':os.path.join('Tensorflow', 'workspace','models',CUSTOM_MODEL_NAME, 'tfliteexport'), 
    'PROTOC_PATH':os.path.join('Tensorflow','protoc')
  }

files = {
    'PIPELINE_CONFIG':os.path.join('Tensorflow', 'workspace','models', CUSTOM_MODEL_NAME, 'pipeline.config'),
    'TF_RECORD_SCRIPT': os.path.join(paths['SCRIPTS_PATH'], TF_RECORD_SCRIPT_NAME), 
    'LABELMAP': os.path.join(paths['ANNOTATION_PATH'], LABEL_MAP_NAME)
}

# for path in paths.values():
#     if not os.path.exists(path):
#         if os.name == 'posix':
#             os.mkdir(path)
#         if os.name == 'nt':
#             os.mkdir(path)

# Load pipeline config and build a detection model
configs = config_util.get_configs_from_pipeline_file(files['PIPELINE_CONFIG'])
detection_model = model_builder.build(model_config=configs['model'], is_training=False)

# Restore checkpoint
ckpt = tf.compat.v2.train.Checkpoint(model=detection_model)
ckpt.restore(os.path.join(paths['CHECKPOINT_PATH'], 'ckpt-11')).expect_partial()

@tf.function
def detect_fn(image):
    image, shapes = detection_model.preprocess(image)
    prediction_dict = detection_model.predict(image, shapes)
    detections = detection_model.postprocess(prediction_dict, shapes)
    return detections

category_index = label_map_util.create_category_index_from_labelmap(files['LABELMAP'])

# Avoid detecting other texts that is not the actual plate number (ex: city name)
def filter_text(region, ocr_result, region_threshold):
    rectangle_size = region.shape[0] * region.shape[1]
    
    plate = []
    
    for result in ocr_result:
        length = np.sum(np.subtract(result[0][1], result[0][0]))
        height = np.sum(np.subtract(result[0][2], result[0][1]))
        
        if (length * height / rectangle_size) > region_threshold:
            plate.append(result[1])
        
        # print(length, width)
    return plate

# put above two OCR sections into one function
# ocr function
def ocr_it(image, detections, detection_threshold, region_threshold):
    
    # Scores, boxes and classes, threshold
    scores = list(filter(lambda x : x> detection_threshold, detections['detection_scores']))
    boxes = detections['detection_boxes'][:len(scores)]
    classes = detections['detection_classes'][:len(scores)]
    
    # Full image dimensions
    width = image.shape[1]
    height = image.shape[0]
    
    print("Found: " + str(len(boxes)) + "Plate(s).")
    # Apply ROI filtering and OCR
    for idx, box in enumerate(boxes):
        roi = box * [height, width, height, width]
        # show region of interest (ROI)
        region = image[int(roi[0]):int(roi[2]),int(roi[1]):int(roi[3])]
        reader = easyocr.Reader(['en'])
        ocr_result = reader.readtext(region)
        
        # print plate texts if is detected
        text = filter_text(region, ocr_result, region_threshold)
        print(text)
        
        # print(ocr_result) (print plate)
        cv2.imshow('image{}'.format(idx), cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
        idx += 1
    
    return text, region

# uuid creates unique image id 
def save_results(text, region, csv_filename, folder_path):
    img_name = '{}.jpg'.format(uuid.uuid1())
    
    # save the detected car plate
    cv2.imwrite(os.path.join(folder_path, img_name), region)
    
    # 將車牌和圖片名稱記錄在csv檔
    with open(csv_filename, mode='a', newline='') as f:
        csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow([img_name,text])

# ========================
# Thresholds
# ========================

region_threshold = 0.6  # to avoid other texts
detection_threshold = 0.3   # this training isn't good enough

# ========================
# Image Detection
# ========================

IMAGE_PATH = os.path.join(paths['IMAGE_PATH'], 'results', 'cars.png')

img = cv2.imread(IMAGE_PATH)
image_np = np.array(img)

input_tensor = tf.convert_to_tensor(np.expand_dims(image_np, 0), dtype=tf.float32)
detections = detect_fn(input_tensor)

num_detections = int(detections.pop('num_detections'))
detections = {key: value[0, :num_detections].numpy()
              for key, value in detections.items()}
detections['num_detections'] = num_detections

# detection_classes should be ints.
detections['detection_classes'] = detections['detection_classes'].astype(np.int64)

label_id_offset = 1
image_np_with_detections = image_np.copy()

# generate bounding boxes
viz_utils.visualize_boxes_and_labels_on_image_array(
            image_np_with_detections,
            detections['detection_boxes'],
            detections['detection_classes']+label_id_offset,
            detections['detection_scores'],
            category_index,
            use_normalized_coordinates=True,
            max_boxes_to_draw=None, # set the number of bounding box, None means show all
            min_score_thresh=.5,    # detection threshold
            agnostic_mode=False)

try:
    text, region = ocr_it(image_np_with_detections, detections, detection_threshold, region_threshold)
    # save_results(text, region,'detection_results.csv', "detection_images")
except:
    pass

ori_img = cv2.cvtColor(image_np_with_detections, cv2.COLOR_BGR2RGB)
cv2.imshow('image1', ori_img)
cv2.waitKey(0)
cv2.destroyAllWindows()
