package com.kayum.aiaagent

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.widget.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import kotlin.concurrent.thread

class MainActivity : Activity() {
 private lateinit var chat: TextView
 private lateinit var input: EditText
 private lateinit var status: TextView
 private var tts: TextToSpeech? = null
 private var speakNext = false
 private val prefs by lazy { getSharedPreferences("agent", MODE_PRIVATE) }
 private val voiceRequestCode = 7301

 override fun onCreate(b: Bundle?) {
  super.onCreate(b); setContentView(R.layout.activity_main)
  chat=findViewById(R.id.chat); input=findViewById(R.id.input); status=findViewById(R.id.status)
  findViewById<Button>(R.id.send).setOnClickListener { send(false) }
  findViewById<Button>(R.id.voice).setOnClickListener { startVoiceInput() }
  findViewById<Button>(R.id.settings).setOnClickListener { settings() }
  findViewById<Button>(R.id.pcTest).setOnClickListener { testPcAgent() }
  tts=TextToSpeech(this) { result ->
   if(result==TextToSpeech.SUCCESS) {
    val engine=tts ?: return@TextToSpeech
    // Set the target language first: setLanguage can reset the active voice.
    val bn=engine.setLanguage(Locale.forLanguageTag("bn-BD"))
    val wantedLanguage = if(bn==TextToSpeech.LANG_MISSING_DATA || bn==TextToSpeech.LANG_NOT_SUPPORTED) {
     engine.setLanguage(Locale.US)
     "en"
    } else "bn"
    applyPreferredVoice(engine, wantedLanguage)
    engine.setPitch(1.12f)
    engine.setSpeechRate(0.96f)
   } else {
    runOnUiThread { status.text = "Siri voice unavailable • check phone Text-to-Speech settings" }
   }
  }
  refreshStatus()
 }

 private fun refreshStatus() {
  val pc=prefs.getString("pc_url", "").orEmpty().trim()
  val token=prefs.getString("pc_token", "").orEmpty().trim()
  status.text = when {
   pc.isNotBlank() && token.isNotBlank() -> "PC Agent: configured"
   pc.isNotBlank() -> "PC Agent URL saved • add token in Settings"
   else -> "Configure PC Agent in Settings"
  }
 }

 private fun send(fromVoice:Boolean) {
  val s=input.text.toString().trim(); if(s.isEmpty()) return
  speakNext=fromVoice
  chat.append("\n\nYou: " + s + "\nAgent: thinking…")
  input.setText("")
  thread {
   val answer = handleAgentRequest(s)
   runOnUiThread {
    chat.append("\n" + answer)
    findViewById<ScrollView>(R.id.scroll).post { findViewById<ScrollView>(R.id.scroll).fullScroll(ScrollView.FOCUS_DOWN) }
    speak(answer)
   }
  }
 }

 private fun handleAgentRequest(prompt:String):String {
  val pc = prefs.getString("pc_url", "").orEmpty().trim()
  val forcePhone = prompt.startsWith("PHONE:", true) || prompt.startsWith("ফোনে")
  val forcePc = prompt.startsWith("PC:", true) || prompt.startsWith("পিসিতে") || prompt.startsWith("কম্পিউটারে")
  val phonePrompt = prompt.replaceFirst(Regex("^(?i:PHONE:|ফোনে)\\s*"), "").trim()
  val pcPrompt = prompt.replaceFirst(Regex("^(?i:PC:|পিসিতে|কম্পিউটারে)\\s*"), "").trim()
  if (forcePhone) {
   return PhoneAgent.handle(this, phonePrompt) ?: "এই phone command এখনো সমর্থিত নয়।"
  }
  // Keep phone-only app actions working even when a PC URL is configured.
  val low = prompt.lowercase()
  val phoneOnlyIntent = listOf("whatsapp", "telegram", "facebook", "play store", "settings", "সেটিং", "সেটিংস", "ফোনে").any { low.contains(it) }
  if (!forcePc && phoneOnlyIntent) {
   val phone = PhoneAgent.handle(this, prompt)
   if (phone != null) return phone
  }
  if (pc.isNotBlank() || forcePc) {
   if (pc.isBlank()) return "PC Agent URL সেটিংসে দিন।"
   val command = pcPrompt
   val token = prefs.getString("pc_token", "").orEmpty().trim()
   if (token.isBlank()) return "PC Agent token নেই। Settings-এ token দিন।"
   val result = sendPcCommandSync(command)
   if (result.startsWith("HTTP 200:")) {
    val body = result.removePrefix("HTTP 200: ")
    try {
     val json = org.json.JSONObject(body)
     val message = json.optString("response").trim()
     if (json.optBoolean("handled", false)) return message.ifBlank { "PC task completed." }
     if (message.isNotBlank()) return message
     return "PC Agent command বুঝেছে, কিন্তু কোনো action সম্পন্ন করেনি।"
    } catch(_:Exception) {
     return "PC Agent থেকে ভুল response এসেছে। PC Agent আপডেট করে আবার চেষ্টা করুন।"
    }
   } else if (result.startsWith("HTTP 401:")) {
    return "PC Agent token ভুল। Settings-এ PC token ঠিক করে আবার চেষ্টা করুন।"
   } else if (result.startsWith("HTTP 404:")) {
    return "PC Agent endpoint পাওয়া যায়নি। Settings-এ PC Agent URL পরীক্ষা করুন।"
   } else if (result.startsWith("PC Agent error:")) {
    return "PC Agent-এ সংযোগ হচ্ছে না। PC-তে server চালু আছে কি না, Wi-Fi একই network-এ কি না, এবং URL/token ঠিক আছে কি না পরীক্ষা করুন। বিস্তারিত: " + result.removePrefix("PC Agent error:").trim()
   } else {
    return "PC Agent-এর অপ্রত্যাশিত response: " + result
   }
  }
  val phone = PhoneAgent.handle(this, prompt)
  if (phone != null) return phone
  return "এই কমান্ডটি সমর্থিত নয়। PC-তে চালাতে 'PC: open Chrome' লিখুন, আর ফোনে চালাতে 'PHONE: open WhatsApp' লিখুন।"
 }

 private fun applyPreferredVoice(engine: TextToSpeech, language: String) {
  val voices = engine.voices.orEmpty()
  fun soundsFemale(v: android.speech.tts.Voice): Boolean {
   val n=v.name.lowercase()
   return n.contains("female") || n.contains("woman") || n.contains("fem") ||
    n.contains("sfg") || n.contains("zira") || n.contains("jenny") ||
    n.contains("aria") || n.contains("samantha") || n.contains("victoria")
  }
  // Prefer a female-sounding voice for the active language, then any female voice.
  val preferred = voices.firstOrNull { it.locale.language.equals(language,true) && soundsFemale(it) }
   ?: voices.firstOrNull { soundsFemale(it) }
   ?: voices.firstOrNull { it.locale.language.equals(language,true) }
  if(preferred!=null) engine.voice=preferred
 }

 private fun speak(text:String) {
  val clean=text.trim(); if(clean.isEmpty()) return
  val engine=tts ?: return
  val r=engine.setLanguage(Locale.forLanguageTag("bn-BD"))
  val language = if(r==TextToSpeech.LANG_MISSING_DATA || r==TextToSpeech.LANG_NOT_SUPPORTED) {
   engine.setLanguage(Locale.US)
   "en"
  } else "bn"
  // Re-apply after setLanguage because some TTS engines reset the selected voice.
  applyPreferredVoice(engine, language)
  engine.setPitch(1.12f)
  engine.setSpeechRate(0.96f)
  engine.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "siri_reply")
 }

 private fun sendPcCommandSync(command:String):String {
  return try {
   val base=prefs.getString("pc_url","").orEmpty().trim()
   if(base.isBlank()) return "PC Agent URL not configured"
   val conn=URL(base.trimEnd('/') + "/api/mobile/command").openConnection() as HttpURLConnection
   conn.requestMethod="POST"; conn.connectTimeout=10000; conn.readTimeout=90000
   conn.setRequestProperty("Content-Type","application/json")
   conn.setRequestProperty("X-PC-Agent-Token", prefs.getString("pc_token", "").orEmpty()); conn.doOutput=true
   conn.outputStream.use { it.write(org.json.JSONObject().put("command",command).toString().toByteArray(Charsets.UTF_8)) }
   val code=conn.responseCode
   val stream=if(code in 200..299) conn.inputStream else conn.errorStream
   "HTTP " + code + ": " + (stream?.bufferedReader()?.use { it.readText() } ?: "")
  } catch(e:Exception) { "PC Agent error: " + (e.message ?: "unknown error") }
 }

 private fun startVoiceInput() {
  try {
   val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "bn-BD")
    putExtra(RecognizerIntent.EXTRA_PROMPT, "বাংলা বা English-এ বলুন")
   }
   startActivityForResult(intent, voiceRequestCode)
  } catch (_: Exception) {
   Toast.makeText(this, "এই ফোনে speech recognition পাওয়া যায়নি।", Toast.LENGTH_LONG).show()
  }
 }

 @Deprecated("Deprecated by Android, kept for broad device compatibility")
 override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
  super.onActivityResult(requestCode, resultCode, data)
  if (requestCode == voiceRequestCode && resultCode == RESULT_OK) {
   val spoken = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
   if (spoken.isNotBlank()) {
    input.setText(spoken)
    send(true)
   }
  }
 }

 private fun testPcAgent() {
  val base=prefs.getString("pc_url", "").orEmpty().trim()
  if (base.isBlank()) {
   status.text = "PC Agent URL not configured"
   Toast.makeText(this, "Settings-এ PC Agent URL দিন।", Toast.LENGTH_LONG).show()
   return
  }
  thread {
   try {
    val token=prefs.getString("pc_token", "").orEmpty().trim()
    if (token.isBlank()) {
     runOnUiThread { status.text = "PC Agent: token missing"; chat.append("\n\nPC Test: FAILED\nSettings-এ PC Agent token দিন।") }
     return@thread
    }
    val conn=URL(base.trimEnd('/') + "/health").openConnection() as HttpURLConnection
    conn.requestMethod="GET"; conn.connectTimeout=5000; conn.readTimeout=5000
    conn.setRequestProperty("X-PC-Agent-Token", token)
    val code=conn.responseCode
    val body=(if(code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
    runOnUiThread {
     if(code in 200..299) { status.text="PC Agent: CONNECTED"; chat.append("\n\nPC Test: CONNECTED\n"+body) }
     else { status.text="PC Agent: HTTP "+code; chat.append("\n\nPC Test: FAILED\nHTTP "+code+"\n"+body) }
    }
   } catch(e:Exception) {
    runOnUiThread { status.text="PC Agent: connection failed"; chat.append("\n\nPC Test: FAILED\n"+(e.message ?: "unknown error")) }
   }
  }
 }

 private fun settings() {
  val box=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(40,10,40,10) }
  val pc=EditText(this).apply { hint="PC Agent URL (e.g. http://192.168.1.5:8765)"; setText(prefs.getString("pc_url","").orEmpty()) }
  val token=EditText(this).apply {
   hint="PC Agent token (from PC console)"
   inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
   setText(prefs.getString("pc_token","").orEmpty())
  }
  box.addView(pc); box.addView(token)
  AlertDialog.Builder(this).setTitle("Siri Settings")
   .setMessage("PC Agent ব্যবহার করতে PC-তে server চালিয়ে URL ও token দিন। Token public share করবেন না.")
   .setView(box).setPositiveButton("Save") { _,_ ->
    prefs.edit().clear().putString("pc_url",pc.text.toString().trim()).putString("pc_token",token.text.toString().trim()).apply(); refreshStatus()
   }.setNegativeButton("Cancel",null).show()
 }

 override fun onDestroy(){
  tts?.stop(); tts?.shutdown(); super.onDestroy()
 }
}