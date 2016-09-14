import os
import io
import json
import urllib2
import requests
import PIL.Image as Image
from bs4 import BeautifulSoup


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

    def search_and_download(self, search_terms, max_n=None):
        if max_n:
            self.max_n = max_n
        self.make_query_string(search_terms)
        return self.download_images(search_terms)

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
                raw_img.save(fp)
                print 'saving ' + img + ' to ' + fp
            except Exception as e:
                print "could not load : " + img + ' ' + str(e)
