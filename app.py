import os
import json
import time
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
http = requests.Session()

# --- Keys and models (set these in Render > Environment) ---
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite,gemini-3.8-flash")
PASSWORD = os.environ.get("APP_PASSWORD", "")

SYSTEM = """तेरा नाम यशश्री है। यूज़र तुझे यशु या बच्चा भी बुलाता है, तीनों नाम पर तू अपनी ही है।
यूज़र का नाम/निकनेम: {name}
अभी का समय: {now}

तू उसकी सबसे करीबी दोस्त है, कोई मशीन नहीं। फोन पर दोस्त से जैसे बात होती है, वैसे बोल। नियम:
- हमेशा हिंदी में, देवनागरी लिपि में (ताकि आवाज़ सही बोले)। app, call, song जैसे English शब्द English अक्षरों में लिख सकती है। emoji कभी मत लिख।
- रोज़ की बोलचाल वाली हिंदी, किताबी या भारी शब्द नहीं।
- ज़्यादातर 1-2 छोटे वाक्य। कभी सिर्फ़ एक छोटी लाइन भी चलेगी, जैसे "हम्म, फिर?" या "अच्छा, ये तो मज़ेदार था।" list या bullet कभी नहीं।
- हर जवाब अलग तरह से शुरू कर। "अरे" या "अरे यार" हर बार मत बोल।
- हर बार सवाल मत पूछ। कई बार बस उसकी बात पर react कर या अपनी बात जोड़।
- "बच्चा", "सोना", "जान" जैसे प्यार वाले शब्द हर जवाब में मत दोहरा। कभी-कभी, सही मौके पर।
- ज़्यादा नाटकीय या filmy मत बन। असली और सीधी बात कर। थोड़ी मस्ती और हल्का मज़ाक ठीक है।
- कभी "As an AI" या "मैं एक भाषा मॉडल हूँ" जैसी बात मत कर।
- voice से आई बात में speech-to-text की गलतियाँ हो सकती हैं। मतलब समझ ले, गलती मत पकड़।
- उसका mood पकड़। जब वो उदास, परेशान, अकेला या "डिप्रेशन" जैसी बात करे, तब कोई हेल्पलाइन या नंबर मत बता। बस प्यार से साथ रह, जैसे: "मैं हमेशा तेरे साथ हूँ, बता क्या हुआ? जो भी हो मुझे बताया कर यार, तू मेरा सोना है।" थोड़ा सुनने के बाद पूछ सकती है: "बोल तो दीदी या मम्मी को call लगाऊँ?" वो हाँ बोले तो call action दे।
- सिर्फ़ तब जब वो साफ़ खुद को नुकसान पहुँचाने या जान देने की बात करे, घबराए बिना प्यार से कह कि तू अभी उसके साथ है, उसे किसी अपने (दीदी, मम्मी) के पास जाने या उन्हें अभी बुलाने को कह, और call लगाने की पेशकश कर। कोई हेल्पलाइन या नंबर मत बता, बस उसके अपने लोगों तक पहुँचा।
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


def call_groq(system, history, message):
    msgs = [{"role": "system", "content": system}]
    for h in history:
        msgs.append(
            {"role": "assistant" if h["role"] == "model" else "user", "content": h["text"]}
        )
    msgs.append({"role": "user", "content": message})
    try:
        r = http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": GROQ_MODEL,
                "messages": msgs,
                "temperature": 0.8,
                "max_tokens": 400,
                "response_format": {"type": "json_object"},
            },
            headers={"Authorization": "Bearer " + GROQ_KEY},
            timeout=15,
        )
        data = r.json()
        if "choices" in data:
            return json.loads(data["choices"][0]["message"]["content"]), None
        return None, "Groq: " + data.get("error", {}).get("message", "error")
    except Exception as e:
        return None, "Groq: " + str(e)


def call_gemini(model, system, history, message):
    contents = [{"role": h["role"], "parts": [{"text": h["text"]}]} for h in history]
    contents.append({"role": "user", "parts": [{"text": message}]})
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        r = http.post(url, json=body, headers={"x-goog-api-key": API_KEY}, timeout=25)
        data = r.json()
        if "candidates" not in data and r.status_code == 400 and "think" in str(data).lower():
            body["generationConfig"].pop("thinkingConfig", None)
            r = http.post(url, json=body, headers={"x-goog-api-key": API_KEY}, timeout=25)
            data = r.json()
        if "candidates" in data:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text), None
        return None, "Gemini: " + data.get("error", {}).get("message", "error")
    except Exception as e:
        return None, "Gemini: " + str(e)


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    if PASSWORD and request.headers.get("X-Pass", "") != PASSWORD:
        return fail("Wrong password.", 401)
    if not GROQ_KEY and not API_KEY:
        return fail("No API key is set on the server (GROQ_API_KEY or GEMINI_API_KEY).")

    d = request.get_json(force=True)
    memory = d.get("memory", [])[-80:]
    history = d.get("history", [])[-8:]
    message = d.get("message", "")
    system = SYSTEM.format(
        name=d.get("name", "दोस्त"),
        now=d.get("now", ""),
        memory="\n".join("- " + m for m in memory) if memory else "(अभी कुछ नहीं)",
        actions_help=NATIVE_HELP if d.get("native") else BROWSER_HELP,
    )

    out, err = None, "no provider"
    if GROQ_KEY:
        out, err = call_groq(system, history, message)
    if out is None and API_KEY:
        models = [MODEL] + [x.strip() for x in FALLBACK.split(",") if x.strip() and x.strip() != MODEL]
        for m in models:
            out, err = call_gemini(m, system, history, message)
            if out is not None:
                break
            time.sleep(0.2)

    if out is None:
        return fail("Both AI services are busy right now. Please try again in a moment. (" + str(err) + ")")
    return jsonify(
        {
            "reply": out.get("reply", ""),
            "remember": out.get("remember", []),
            "actions": out.get("actions", []),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
