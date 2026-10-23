from PIL import ImageGrab
im = ImageGrab.grab()
print("size:", im.size)
im.save(r"D:\EE Reverse\answers\out\_shot_now.png")
