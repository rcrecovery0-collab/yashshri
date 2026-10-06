package com.yashshri.assistant;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.AlarmClock;
import android.provider.ContactsContract;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {

    // CHANGE THIS to your Render link
    static final String APP_URL = "https://YOUR-APP-NAME.onrender.com";

    WebView web;
    SpeechRecognizer recognizer;
    TextToSpeech tts;
    boolean ttsReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);

        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(), "Android");

        requestPermissions(new String[]{
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.READ_CONTACTS,
                Manifest.permission.CALL_PHONE
        }, 1);

        tts = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(new Locale("hi", "IN"));
                tts.setPitch(1.1f);
                ttsReady = true;
            }
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { js("onNativeSpeakStart()"); }
            @Override public void onDone(String id) { js("onNativeSpeakDone()"); }
            @Override public void onError(String id) { js("onNativeSpeakDone()"); }
        });

        web.loadUrl(APP_URL);
    }

    void js(String code) {
        runOnUiThread(() -> web.evaluateJavascript(code, null));
    }

    void toast(String msg) {
        runOnUiThread(() -> Toast.makeText(this, msg, Toast.LENGTH_SHORT).show());
    }

    String resolveNumber(String target) {
        if (target == null) return null;
        String t = target.trim();
        if (t.matches("[+0-9 ()\\-]{5,}")) return t.replaceAll("[ ()\\-]", "");
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) return null;
        Cursor c = getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                new String[]{ContactsContract.CommonDataKinds.Phone.NUMBER},
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?",
                new String[]{"%" + t + "%"},
                null);
        if (c != null) {
            try {
                if (c.moveToFirst()) return c.getString(0);
            } finally {
                c.close();
            }
        }
        return null;
    }

    class Bridge {

        @JavascriptInterface
        public void startListening() {
            runOnUiThread(() -> {
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 2);
                    toast("Allow the microphone, then tap again");
                    js("onNativeListenEnd('')");
                    return;
                }
                if (!SpeechRecognizer.isRecognitionAvailable(MainActivity.this)) {
                    toast("Speech recognition is not available on this phone");
                    js("onNativeListenEnd('')");
                    return;
                }
                if (recognizer != null) recognizer.destroy();
                recognizer = SpeechRecognizer.createSpeechRecognizer(MainActivity.this);
                recognizer.setRecognitionListener(new RecognitionListener() {
                    @Override public void onReadyForSpeech(Bundle params) {}
                    @Override public void onBeginningOfSpeech() {}
                    @Override public void onRmsChanged(float rmsdB) {}
                    @Override public void onBufferReceived(byte[] buffer) {}
                    @Override public void onEndOfSpeech() {}
                    @Override public void onEvent(int eventType, Bundle params) {}

                    @Override public void onError(int error) {
                        js("onNativeListenEnd('')");
                    }

                    @Override public void onResults(Bundle results) {
                        ArrayList<String> l = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        String t = (l != null && !l.isEmpty()) ? l.get(0) : "";
                        js("onNativeListenEnd(" + JSONObject.quote(t) + ")");
                    }

                    @Override public void onPartialResults(Bundle partial) {
                        ArrayList<String> l = partial.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        if (l != null && !l.isEmpty()) {
                            js("onNativePartial(" + JSONObject.quote(l.get(0)) + ")");
                        }
                    }
                });
                Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN");
                i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
                recognizer.startListening(i);
            });
        }

        @JavascriptInterface
        public void stopListening() {
            runOnUiThread(() -> {
                if (recognizer != null) recognizer.stopListening();
            });
        }

        @JavascriptInterface
        public void speak(String text) {
            if (!ttsReady) {
                js("onNativeSpeakDone()");
                return;
            }
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "ys");
        }

        @JavascriptInterface
        public void stopSpeaking() {
            if (tts != null) tts.stop();
        }

        @JavascriptInterface
        public void call(String target) {
            runOnUiThread(() -> {
                String number = resolveNumber(target);
                if (number == null) {
                    toast("Could not find a number for: " + target);
                    return;
                }
                Uri u = Uri.parse("tel:" + Uri.encode(number));
                Intent i;
                if (checkSelfPermission(Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
                    i = new Intent(Intent.ACTION_CALL, u);
                } else {
                    i = new Intent(Intent.ACTION_DIAL, u);
                }
                startActivity(i);
            });
        }

        @JavascriptInterface
        public void alarm(int hour, int minute, String label) {
            runOnUiThread(() -> {
                Intent i = new Intent(AlarmClock.ACTION_SET_ALARM);
                i.putExtra(AlarmClock.EXTRA_HOUR, hour);
                i.putExtra(AlarmClock.EXTRA_MINUTES, minute);
                i.putExtra(AlarmClock.EXTRA_MESSAGE, label);
                i.putExtra(AlarmClock.EXTRA_SKIP_UI, true);
                try {
                    startActivity(i);
                } catch (Exception e) {
                    toast("Could not set the alarm");
                }
            });
        }

        @JavascriptInterface
        public void timer(int seconds, String label) {
            runOnUiThread(() -> {
                Intent i = new Intent(AlarmClock.ACTION_SET_TIMER);
                i.putExtra(AlarmClock.EXTRA_LENGTH, seconds);
                i.putExtra(AlarmClock.EXTRA_MESSAGE, label);
                i.putExtra(AlarmClock.EXTRA_SKIP_UI, true);
                try {
                    startActivity(i);
                } catch (Exception e) {
                    toast("Could not set the timer");
                }
            });
        }

        @JavascriptInterface
        public void openApp(String name) {
            runOnUiThread(() -> {
                PackageManager pm = getPackageManager();
                String q = name == null ? "" : name.toLowerCase().trim();
                if (q.isEmpty()) return;
                for (ApplicationInfo ai : pm.getInstalledApplications(0)) {
                    String label = pm.getApplicationLabel(ai).toString().toLowerCase();
                    if (label.contains(q)) {
                        Intent i = pm.getLaunchIntentForPackage(ai.packageName);
                        if (i != null) {
                            startActivity(i);
                            return;
                        }
                    }
                }
                toast("App not found: " + name);
            });
        }

        @JavascriptInterface
        public void openUrl(String url) {
            runOnUiThread(() -> {
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception e) {
                    toast("Could not open the link");
                }
            });
        }
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (recognizer != null) recognizer.destroy();
        if (tts != null) tts.shutdown();
        super.onDestroy();
    }
            }
