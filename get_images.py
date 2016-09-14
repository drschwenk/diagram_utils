import os
import io
import json
import urllib2
import requests
import PIL.Image as Image
from bs4 import BeautifulSoup
from PIL import Image
import numpy as np
import os
import glob
import imagehash


class DiagramFinder(object):

    def __init__(self, outdir='candidate_diagrams', min_img_size=500, max_img_size=1500):
        self.output_dir = outdir
        self.max_img_dim = max_img_size
        self.min_img_size = min_img_size
        self.header = {'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.134 Safari/537.36"}
        self.base_search_url = "https://www.google.co.in/search?q={}&source=lnms&tbm=isch"
        self.full_size_images = []
        self.queries_made = []
        self.max_n = 10

    def scale_image(self, d_img):
        img_size = d_img.size
        if max(img_size) < self.min_img_size:
            return False
        scale_factor = self.max_img_dim / float(max(img_size))
        img_dim = tuple([int(dim * scale_factor) for dim in img_size])
        d_img.thumbnail(img_dim, Image.ANTIALIAS)
        return True

    def image3d(self, original_image):
        # This ensures that the transparent pixels (if any) are set to white (255, 255, 255)
        original_image = original_image.convert('RGBA')
        background = Image.new('RGBA', original_image.size, (255, 255, 255))
        background.paste(original_image, mask=original_image.split()[3])  # 3 is the alpha channel
        rgb_image = background.convert('RGB')
        img = np.array(rgb_image)
        img_size = np.shape(img)
        # Check to see if the image is a 3-channel RGB image
        if len(img_size) != 3:
            raise ValueError('Image has not been converted to a 3 channel RGB format!')
        return rgb_image

    def search_and_download(self, search_terms, max_n=None):
        if max_n:
            self.max_n = max_n
        self.make_query_string(search_terms)
        self.download_images(search_terms)

    def make_query_string(self, query):
        query = query.split()
        query = '+'.join(query)
        search_url = self.base_search_url.format(query)
        req = requests.get(search_url, headers=self.header)
        soup = BeautifulSoup(req.text, 'html.parser')
        for a in soup.find_all("div", {"class": "rg_meta"})[:self.max_n]:
            link, image_type = json.loads(a.text)["ou"], json.loads(a.text)["ity"]
            self.full_size_images.append((link, image_type))
        print "there are ", len(self.full_size_images), " images to download"

    def download_images(self, query):
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        output_query_path = os.path.join(self.output_dir, query.replace(' ', '_'))
        if not os.path.exists(output_query_path):
            os.mkdir(output_query_path)
        for i, (img, image_type) in enumerate(self.full_size_images):
            try:
                req = requests.get(img)
                raw_img = Image.open(io.BytesIO(req.content))
                if not self.scale_image(raw_img):
                    continue
                img_number = len(os.listdir(output_query_path)) + 1
                if not image_type:
                    fp = os.path.join(output_query_path, 'diagram' + "_" + str(img_number) + ".jpg")
                else:
                    fp = os.path.join(output_query_path, 'diagram' + "_" + str(img_number) + '.' + image_type)
                converted_image = self.image3d(raw_img)
                converted_image.save(fp)
                print 'saving ' + img + ' to ' + fp
            except Exception as e:
                print "could not load : " + img + ' ' + str(e)


class DiagramDeDuper(object):
    def __init__(self):
        self.image_hashes = {}
        self.images_seen = set()
        self.image_ext = ['*.JPG', '*.PNG', '*.GIF', '*.BMP', '*.JPEG', '*.TIFF']
        self.image_ext += [img_type.lower() for img_type in self.image_ext]

    def get_image_paths(self, in_dir):
        image_paths = []
        for extension in self.image_ext:
            image_paths.extend(glob.glob(os.path.join(in_dir, extension)))
        return image_paths



    def get_hashes(self, image):
        ahash = imagehash.average_hash(image)
        dhash = imagehash.dhash(image)
        phash = imagehash.phash(image)
        combined_hash = ''.join(str(x) for x in [ahash, dhash, phash])
        return ahash, dhash, phash, combined_hash

    def precompute_static_img_hashes(self, static_dir):
        static_image_paths = self.get_image_paths(static_dir)
        for current_image_path in static_image_paths:
            if current_image_path in self.images_seen:
                continue
            image = Image.open(current_image_path)
            ahash, dhash, phash, combined_hash = self.get_hashes(image)
            hash_and_size = (os.path.split(current_image_path)[1], image.size)
            hash_to_use = ahash
            self.image_hashes[hash_to_use] = [hash_and_size]
            self.images_seen.add(current_image_path)

    def detect_image_dups(self, in_dir):
        image_paths = self.get_image_paths(in_dir)
        for current_image_path in image_paths:
            if current_image_path in self.images_seen:
                continue
            try:
                image = Image.open(current_image_path)
            except IOError as e:
                broken_path = current_image_path.replace('candidate_diagrams', 'broken_images')
                print broken_path
                os.rename(current_image_path, broken_path)
            ahash, dhash, phash, combined_hash = self.get_hashes(image)
            hash_and_size = (os.path.split(current_image_path)[1], image.size)
            hash_to_use = ahash
            if hash_to_use in self.image_hashes:
                self.image_hashes[hash_to_use].append(hash_and_size)
            else:
                self.image_hashes[hash_to_use] = [hash_and_size]
            self.images_seen.add(current_image_path)
        return list(self.image_hashes.values())

    def detect_dupes_single_image_file(self, current_image_path):
        if current_image_path in self.images_seen:
            return
        try:
            image = Image.open(current_image_path)
        except IOError as e:
            broken_path = current_image_path.replace('candidate_diagrams', 'broken_images')
            print broken_path
        ahash, dhash, phash, combined_hash = self.get_hashes(image)
        hash_and_size = (os.path.split(current_image_path)[1], image.size)
        hash_to_use = ahash
        if hash_to_use in self.image_hashes:
            self.image_hashes[hash_to_use].append(hash_and_size)
        else:
            self.image_hashes[hash_to_use] = [hash_and_size]
        self.images_seen.add(current_image_path)
        return list(self.image_hashes[hash_to_use])

    def summarize_dupes(self):
        return pd.Series([len(h) for h in self.image_hashes.values()]).value_counts()