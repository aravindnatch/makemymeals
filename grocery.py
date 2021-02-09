from flask import Flask, render_template, redirect, request, session, make_response
import requests
import os
import time
import json
from PIL import Image, ImageDraw, ImageFont

headers = {
  'content-type': 'application/json',
  'nep-organization': 'fba3b52c94954a4695c821eeaf6d8f66'
}

#tf
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
from imageai.Detection import ObjectDetection
detector = ObjectDetection()
detector.setModelTypeAsRetinaNet()
detector.setModelPath("resnet50_coco_best_v2.1.0.h5")
detector.loadModel()

app = Flask(__name__)

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/checkout")
def checkout():
    return render_template('checkout.html')

@app.route("/recipe", methods=['GET', 'POST'])
def upload():
    try:
        filename = ''
        if request.method == 'POST':
            f = request.files['file']
            extension = f.filename
            extension = extension.split(".")[1]
            filename = str(time.time()).split(".")[0] + "." + extension
            f.save('input_images/' + filename)

        detections = detector.detectObjectsFromImage(input_image='input_images/' + filename, output_image_path='output_images/' + filename)

        for eachObject in detections:
            item = eachObject["name"]
            prob = eachObject["percentage_probability"]
            break

        ingredient = item
        ncrData = {}
        for x in range(12):
            getItem = requests.get(f"https://gateway-staging.ncrcloud.com/catalog/items/{x}", headers=headers, auth=("1c4e49d2-289b-4021-bae3-538df0b7a5e4","12345678"))
            getItem = getItem.json()
            ncrData[getItem['shortDescription']['values'][0]['value']] = getItem['dynamicAttributes'][0]['attributes'][0]['value']

        # get recipes from database
        with open('recipe.json') as f:
            data = json.load(f)
            recipelist = []
            recipenames = []

        for x in data:
            ingredients = data[x].split("&")

            if ingredient in ingredients:
                recipelist.append(ingredients)
                recipenames.append(x)
        recip = []
        county = 0
        for x in recipenames:
            temparr = []
            temparr.append(county)
            temparr.append(' '.join(x.title().split("_")))
            recip.append(temparr)
            county+=1
        return render_template('recipe.html', ingredient=ingredient.title(),recipenames=recip)
    except Exception as e:
        print(str(e))
        return('could not determine item')

@app.route("/storemap/")
def storemap():
    ingredient = request.args.get("ing").lower()
    chosenRecipe = int(request.args.get("recipe"))

    # get items from ncr
    ncrData = {}
    tempitems = []
    for x in range(12):
        getItem = requests.get(f"https://gateway-staging.ncrcloud.com/catalog/items/{x}", headers=headers, auth=("1c4e49d2-289b-4021-bae3-538df0b7a5e4","12345678"))
        getItem = getItem.json()
        tempitems.append(getItem['dynamicAttributes'][0]['attributes'][0]['value'])
        ncrData[getItem['shortDescription']['values'][0]['value']] = getItem['dynamicAttributes'][0]['attributes'][0]['value']

    # get recipes from database
    with open('recipe.json') as f:
        data = json.load(f)

    recipelist = []
    recipenames = []
    for x in data:
        ingredients = data[x].split("&")
        if ingredient in ingredients:
            recipelist.append(ingredients)
            recipenames.append(x)

    # get shortest path to items
    items = []
    # get current locatino of user
    my_x = int(ncrData[ingredient][0])
    my_y = int(ncrData[ingredient][1])
    # iterate through matched recipes

    final_dist = []

    left = []
    for ing in recipelist[chosenRecipe]:
        left.append(ing)
    left.remove(ingredient)
    #print(left)
    while(len(left) > 0):
        dist_to_items = []
        for ing in left:
            x_loc = int(ncrData[ing][0])
            y_loc = int(ncrData[ing][1])
            if x_loc == my_x:
                dist = abs(my_y-y_loc)
            else:
                dist = ((2-my_y) +(2-y_loc) + abs(x_loc-my_x))
            dist_to_items.append((dist, ing))
        dist_to_items.sort()
        left.remove(dist_to_items[0][1])
        my_x = int(ncrData[dist_to_items[0][1]][0])
        my_y = int(ncrData[dist_to_items[0][1]][1])
        final_dist.append((dist_to_items[0][0], dist_to_items[0][1]))
        items.append(dist_to_items)


    # items = 2d array
    aislemap = [15,150,300,460,600]
    aislecoords = [15,158,308,458,600]
    insidemap = [75,222,370]

    # create image with path__
    base = Image.open("original.jpg").convert("RGBA")

    # make a blank image for the text, initialized to transparent text color
    txt = Image.new("RGBA", base.size, (255,255,255,0))

    # get a font
    fnt = ImageFont.truetype("roboto.ttf", 40)
    fnt2 = ImageFont.truetype("OpenSansEmoji.ttf", 40)
    # get a drawing context
    d = ImageDraw.Draw(txt)
    c = 1


    x = int(ncrData[ingredient][0])
    y = int(ncrData[ingredient][1])
    d.text((insidemap[y]-2,aislecoords[x]-3), '?', font=fnt2, fill=(0, 0, 0,255))
    d.line([(570, 628), (570, 35)], fill=(128, 180, 251,255), width=7, joint=None)

    #d.line([(95, 38), (202, 38)], fill=(255, 80, 80,255), width=7, joint=None)

    items_in_aisle = {0: [], 1: [], 2: [], 3: [], 4: []}
    row_items = {15: 0, 150: 1, 300: 2, 460: 3, 600: 4}
    linesy = [38, 182, 332, 480, 625]
    linesx = []

    items_in_aisle[row_items[aislemap[x]]].append(insidemap[y])

    finalRecipeCoords = []
    for ing in final_dist:
        x = int(ncrData[ing[1]][0])
        y = int(ncrData[ing[1]][1])
        temp = []
        temp.append(x)
        temp.append(y)
        finalRecipeCoords.append(temp)
        d.ellipse((insidemap[y], aislemap[x], insidemap[y], aislemap[x]), fill='red', width=5, outline ='red')
        d.text((insidemap[y],aislecoords[x]), str(c), font=fnt, fill=(0,0,0,200))
        items_in_aisle[row_items[aislemap[x]]].append(insidemap[y])
        c+=1
    for key in items_in_aisle.keys():
        if len(items_in_aisle[key]) == 0:
            continue
        v = items_in_aisle[key]
        v.sort()
        if len(v) == 1:
            d.line([(v[0]+30, linesy[key]), (570, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)
        elif len(v) == 2:
            d.line([(v[0]+30, linesy[key]), (v[1]-5, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)
            d.line([(v[1]+30, linesy[key]), (570, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)
        else:
            d.line([(v[0]+30, linesy[key]), (v[1]-30, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)
            d.line([(v[1]+30, linesy[key]), (v[2]-30, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)
            d.line([(v[2]+30, linesy[key]), (570, linesy[key])], fill=(128, 180, 251,255), width=7, joint=None)

    out = Image.alpha_composite(base, txt)
    outfile = str(time.time()).split(".")[0]
    out.save(f'static/new_images/{outfile}.png', 'PNG')
    outfile = 'new_images/' + outfile + '.png'

    temp2arr = []
    temp2arr.append(int(ncrData[ingredient][0]))
    temp2arr.append(int(ncrData[ingredient][1]))
    finalRecipeCoords.insert(0, temp2arr)

    recipeinfo = []
    numletter = 'ABCDE'
    for x in range(len(recipelist[chosenRecipe])):
        temp3 = []
        temp3.append(' '.join(recipelist[chosenRecipe][x].title().split("_")))
        aislestr = ''
        aislestr+=numletter[finalRecipeCoords[x][0]]
        aislestr+=str(finalRecipeCoords[x][1]+1)
        temp3.append(aislestr)
        recipeinfo.append(temp3)

    recipename = ' '.join(recipenames[chosenRecipe].title().split("_"))
    return render_template('map.html', ingredients=recipeinfo, ingredient=ingredient, recipename=recipename, outfile=outfile)

