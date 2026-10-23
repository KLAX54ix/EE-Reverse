from PIL import ImageGrab
im = ImageGrab.grab()
im.save(r"D:\EE Reverse\answers\out\_shot_after_wheel.png")
print("saved", im.size)
