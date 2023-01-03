from bs4 import BeautifulSoup
import requests
import re
import urllib
import os

def get_soup(url,header):
  return BeautifulSoup(urllib.request.urlopen(urllib.request.Request(url,headers=header)), features="lxml")


def dl_cover(q, outdir):
    # you can change the query for the image  here 
    
    query= (q+" high resolution").split()
    query='+'.join(query)
    url="https://www.google.com/search?q="+ query + "&tbm=isch&ved=2ahUKEwjB87mv06r8AhVDCUQIHTQyBksQ2-cCegQIABAA&oq=Nicki+Minaj+-+Anaconda&gs_lcp=CgNpbWcQAzoECCMQJzoICAAQgAQQsQM6BwgAELEDEEM6BQgAEIAEOgYIABAHEB5Q5hBYkyxg7i5oAHAAeACAAbICiAH-C5IBCDEwLjQuMC4xmAEAoAEBqgELZ3dzLXdpei1pbWfAAQE&sclient=img&ei=2rqzY8GeNsOSkPIPtOSY2AQ&bih=827&biw=853"

    print("url:", url)
    header = {'User-Agent': 'Mozilla/5.0'} 
    soup = get_soup(url, header)

    images = [a['src'] for a in soup.find_all("img", {"src": re.compile("gstatic.com")})]
    
    print("img_link", images[0])
    img_type = ".jpg" #images[0].split('.')[-1]
    
    raw_img = urllib.request.urlopen(images[0]).read()
    
    with open(outdir+q+img_type, 'wb') as f:
        f.write(raw_img)

if __name__ == "__main__":
    outdir = "./"
    q = "Nicki Minaj - Anaconda"
    dl_cover(q, outdir)