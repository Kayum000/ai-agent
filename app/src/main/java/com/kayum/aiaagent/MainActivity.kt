package com.kayum.aiaagent

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
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
 private val models = listOf("gemini-2.5-flash-lite", "gemini-2.5-flash")
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
    val engine=tts
    val female=engine?.voices?.filter { v ->
     val n=v.name.lowercase(); val l=v.locale.language.lowercase()
     (n.contains("female") || n.contains("woman") || n.contains("fem") || n.contains("sfg")) && l in setOf("bn","en","hi")
    }?.firstOrNull() ?: engine?.voices?.firstOrNull { v ->
     val n=v.name.lowercase()
     n.contains("female") || n.contains("woman") || n.contains("fem") || n.contains("sfg")
    }
    if(female!=null) engine?.voice=female
    val bn=engine?.setLanguage(Locale.forLanguageTag("bn-BD")) ?: TextToSpeech.ERROR
    if(bn==TextToSpeech.LANG_MISSING_DATA || bn==TextToSpeech.LANG_NOT_SUPPORTED) engine?.setLanguage(Locale.US)
    engine?.setPitch(1.12f)
    engine?.setSpeechRate(0.96f)
   }
  }
  refreshStatus()
 }

 private fun refreshStatus() {
  val pc=prefs.getString("pc_url", "").orEmpty().trim()
  val token=prefs.getString("pc_token", "").orEmpty().trim()
  val cloud=prefs.getString("gemini_key", "").orEmpty().isNotBlank()
  status.text = when {
   pc.isNotBlank() && token.isNotBlank() -> "PC Agent: configured • Cloud AI: " + if (cloud) "ready" else "add Gemini key"
   pc.isNotBlank() -> "PC Agent URL saved • add token in Settings"
   cloud -> "Cloud AI: Gemini ready • PC Agent optional"
   else -> "Add Gemini key in Settings • PC Agent optional"
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
    if(speakNext) speak(answer)
   }
  }
 }

 private fun handleAgentRequest(prompt:String):String {
  val pc = prefs.getString("pc_url", "").orEmpty().trim()
  if (pc.isNotBlank()) {
   val command = prompt.removePrefix("PC:").removePrefix("pc:").trim()
   val result = sendPcCommandSync(command)
   if (result.startsWith("HTTP 200:")) {
    val body = result.removePrefix("HTTP 200: ")
    try {
     val json = org.json.JSONObject(body)
     if (json.optBoolean("handled", false)) return json.optString("response").ifBlank { "PC task completed." }
    } catch(_:Exception) { }
   } else if (result.startsWith("HTTP 401:")) {
    return "PC Agent token ভুল। Settings-এ PC token ঠিক করে আবার চেষ্টা করুন।"
   } else if (result.startsWith("HTTP 404:")) {
    return "PC Agent endpoint পাওয়া যায়নি। Settings-এ PC Agent URL পরীক্ষা করুন।"
   }
  }
  val phone = PhoneAgent.handle(this, prompt)
  if (phone != null && !phone.startsWith("Phone Control চালু নেই")) return phone
  return askGemini(prompt)
 }

 private fun speak(text:String) {
  val clean=text.trim(); if(clean.isEmpty()) return
  val r=tts?.setLanguage(Locale.forLanguageTag("bn-BD")) ?: TextToSpeech.ERROR
  if(r==TextToSpeech.LANG_MISSING_DATA || r==TextToSpeech.LANG_NOT_SUPPORTED) tts?.setLanguage(Locale.US)
  tts?.setPitch(1.12f)
  tts?.setSpeechRate(0.96f)
  tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "siri_reply")
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

 private fun askGemini(prompt:String):String {
  val key=prefs.getString("gemini_key","").orEmpty()
  if(key.isBlank()) return "Gemini key সেট করা নেই। ⚙ Settings খুলে আপনার নিজের API key দিন।"
  var lastError = ""
  for (model in models) {
   try {
    val url=URL("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent")
    val conn=url.openConnection() as HttpURLConnection
    conn.requestMethod="POST"; conn.connectTimeout=20000; conn.readTimeout=60000
    conn.setRequestProperty("Content-Type","application/json"); conn.setRequestProperty("x-goog-api-key",key); conn.doOutput=true
    val body=org.json.JSONObject().put("contents", org.json.JSONArray().put(
     org.json.JSONObject().put("parts", org.json.JSONArray().put(org.json.JSONObject().put("text",
      "You are My PC AI Agent. Answer clearly in Bengali or English matching the user. Never claim you performed a phone or PC action unless the app has confirmed it succeeded. If an action was not executed, explain that honestly. User request: " + prompt
     )))
    )).toString()
    conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
    val code=conn.responseCode
    val stream=if(code in 200..299) conn.inputStream else conn.errorStream
    val text=stream?.bufferedReader()?.use { it.readText() } ?: ""
    if(code in 200..299) {
     return org.json.JSONObject(text).optJSONArray("candidates")?.optJSONObject(0)?.optJSONObject("content")
      ?.optJSONArray("parts")?.optJSONObject(0)?.optString("text")
      ?.takeIf { it.isNotBlank() } ?: "AI কোনো text response দেয়নি।"
    }
    lastError = "model=$model HTTP $code " + runCatching {
     org.json.JSONObject(text).optJSONObject("error")?.optString("message")
    }.getOrNull().orEmpty()
   } catch(e:Exception) {
    lastError = "model=$model " + (e.message ?: "unknown error")
   }
  }
  return "Cloud AI সব configured model-এ কাজ করেনি। $lastError"
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
    val conn=URL(base.trimEnd('/') + "/health").openConnection() as HttpURLConnection
    conn.requestMethod="GET"; conn.connectTimeout=5000; conn.readTimeout=5000
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
  val key=EditText(this).apply {
   hint="Gemini API key"; inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
   setText(prefs.getString("gemini_key",""))
  }
  val pc=EditText(this).apply { hint="PC Agent URL (e.g. http://192.168.1.5:8765)"; setText(prefs.getString("pc_url","").orEmpty()) }
  val token=EditText(this).apply {
   hint="PC Agent token (from PC console)"
   inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
   setText(prefs.getString("pc_token","").orEmpty())
  }
  box.addView(key); box.addView(pc); box.addView(token)
  AlertDialog.Builder(this).setTitle("AI Settings")
   .setMessage("Gemini ফোনে সরাসরি কাজ করে। PC Agent ব্যবহার করতে PC-তে server চালিয়ে URL ও token দিন। Token public share করবেন না.")
   .setView(box).setPositiveButton("Save") { _,_ ->
    prefs.edit().putString("gemini_key",key.text.toString().trim()).putString("pc_url",pc.text.toString().trim()).putString("pc_token",token.text.toString().trim()).apply(); refreshStatus()
   }.setNegativeButton("Cancel",null).show()
 }

 override fun onDestroy(){
  tts?.stop(); tts?.shutdown(); super.onDestroy()
 }
}