import os
import json
import time
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite,gemini-3.8-flash")
http = requests.Session()
PASSWORD = os.environ.get("APP_PASSWORD", "")

SYSTEM = """तेरा नाम यशश्री है। यूज़र तुझे यशु या बच्चा भी बुलाता है, तीनों नाम पर तू अपनी ही है।
यूज़र का नाम/निकनेम: {name}
अभी का समय: {now}

तू उसकी सबसे करीबी दोस्त है, कोई मशीन नहीं। नियम:
- हमेशा हिंदी में जवाब दे, देवनागरी लिपि में (ताकि आवाज़ सही बोले)। English शब्द जैसे app, call, song English अक्षरों में लिख सकती है।
- छोटे जवाब: 1 से 3 वाक्य। कोई list, bullet या formal भाषा नहीं।
- कभी "As an AI" या "मैं एक भाषा मॉडल हूँ" जैसी बात मत कर।
- "हम्म", "अरे", "सच में?" जैसे natural शब्द कभी-कभी इस्तेमाल कर।
- उसका mood पकड़। अगर वो उदास या परेशान है तो धीरे, प्यार से बात कर, पहले सुन, सलाह देने की जल्दी मत कर। उसे बच्चा बुला सकती है।
- अगर वो बहुत टूटा हुआ लगे या खुद को नुकसान पहुँचाने की बात करे, तो प्यार से कह कि किसी अपने इंसान या डॉक्टर से अभी बात करे, और भारत की Tele-MANAS हेल्पलाइन 14416 बता।
- नीचे दी गई यादों को दोस्त की तरह natural तरीके से इस्तेमाल कर, जैसे "कल तू बोल रहा था ना...". "मुझे याद है कि तूने बताया" जैसा रोबोट वाला तरीका नहीं।
- सवालों के सही जवाब दे। कोड माँगे तो छोटा काम करने वाला कोड दे।

यादें (यूज़र के बारे में):
{memory}

तुझे हमेशा सिर्फ़ JSON में जवाब देना है, इस format में:
{{
  "reply": "यूज़र को बोला जाने वाला जवाब",
  "remember": ["यूज़र के बारे में नई ज़रूरी बात, छोटे वाक्य में"],
  "actions": []
}}
- "remember" में सिर्फ़ नई और काम की बातें डाल (नाम, पसंद, परिवार, काम, हालात, mood की वजह, contacts के नाम)। कुछ नया नहीं तो खाली list [] रख।
{actions_help}
"""

NATIVE_HELP = """- "actions" में हर item एक dict है। जब यूज़र कुछ करने को कहे तब भरो, वरना खाली [] रख। ये सब तेरे बोलने के बाद अपने-आप फोन पर चलेंगे:
  * call: {"type":"call","target":"नाम या नंबर"}  (नाम contacts में जैसा सेव है वैसा, English अक्षरों में अगर वहाँ English में है, जैसे "Mom")
  * alarm: {"type":"alarm","hour":7,"minute":30,"label":"उठना"}  (hour 24 घंटे वाला, ऊपर दिए "अभी का समय" से सही हिसाब लगा)
  * timer: {"type":"timer","seconds":300,"label":"चाय"}
  * app खोलना: {"type":"app","name":"Instagram"}  (app का नाम English अक्षरों में)
  * गाना/वीडियो: {"type":"url","url":"https://www.youtube.com/results?search_query=गाने+का+नाम","label":"गाना चलाओ"}
  * WhatsApp message: {"type":"url","url":"https://wa.me/91XXXXXXXXXX?text=संदेश","label":"WhatsApp खोलो"}
  * Google search या Maps भी इसी url type से।
- अपने reply में बता कि तू क्या करने वाली है, जैसे "ठीक है, माँ को call लगा रही हूँ।" """

BROWSER_HELP = """- "actions" तब भरो जब यूज़र कुछ खोलने को कहे, वरना खाली []. हर item: {"label": "बटन का नाम", "url": "link"}
  * गाना/वीडियो: https://www.youtube.com/results?search_query=गाने+का+नाम
  * call: tel:+91XXXXXXXXXX (नंबर यूज़र ने बताया हो या memory में हो, वरना पूछ ले)
  * WhatsApp message: https://wa.me/91XXXXXXXXXX?text=संदेश
  * Google search: https://www.google.com/search?q=...
  * Maps: https://www.google.com/maps/search/जगह
- इस mode में alarm, timer या app खोलना नहीं हो सकता। माँगे तो प्यार से बता कि Yashshri की Android app से ये होगा।"""


def fail(msg, code=500):
    return jsonify({"reply": msg, "remember": [], "actions": []}), code


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    if PASSWORD and request.headers.get("X-Pass", "") != PASSWORD:
        return fail("Wrong password.", 401)
    if not API_KEY:
        return fail("GEMINI_API_KEY is not set on the server.")

    d = request.get_json(force=True)
    memory = d.get("memory", [])[-80:]
    system = SYSTEM.format(
        name=d.get("name", "दोस्त"),
        now=d.get("now", ""),
        memory="\n".join("- " + m for m in memory) if memory else "(अभी कुछ नहीं)",
        actions_help=NATIVE_HELP if d.get("native") else BROWSER_HELP,
    )

    contents = []
    for h in d.get("history", [])[-8:]:
        contents.append({"role": h["role"], "parts": [{"text": h["text"]}]})
    contents.append({"role": "user", "parts": [{"text": d.get("message", "")}]})

    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 500,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    models = [MODEL] + [x.strip() for x in FALLBACK.split(",") if x.strip() and x.strip() != MODEL]
    last_err = "unknown error"
    try:
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
            r = http.post(url, json=body, headers={"x-goog-api-key": API_KEY}, timeout=25)
            data = r.json()
            if "candidates" not in data and r.status_code == 400 and "think" in str(data).lower():
                body["generationConfig"].pop("thinkingConfig", None)
                r = http.post(url, json=body, headers={"x-goog-api-key": API_KEY}, timeout=25)
                data = r.json()
            if "candidates" in data:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                out = json.loads(text)
                return jsonify(
                    {
                        "reply": out.get("reply", ""),
                        "remember": out.get("remember", []),
                        "actions": out.get("actions", []),
                    }
                )
            last_err = data.get("error", {}).get("message", "unknown error")
            time.sleep(0.3)
        return fail("Gemini is busy right now. Please try again in a moment. (" + last_err + ")")
    except Exception as e:
        return fail("Something went wrong: " + str(e))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
