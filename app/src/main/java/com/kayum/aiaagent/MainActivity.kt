package com.kayum.aiaagent

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
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
 private val voiceReq=42
 private val prefs by lazy { getSharedPreferences("agent", MODE_PRIVATE) }
 private val model = "gemini-3.5-flash-lite"
 private val pcToken = "mmc-local-test-token"

 override fun onCreate(b: Bundle?) {
  super.onCreate(b); setContentView(R.layout.activity_main)
  chat=findViewById(R.id.chat); input=findViewById(R.id.input); status=findViewById(R.id.status)
  findViewById<Button>(R.id.send).setOnClickListener { send(false) }
  findViewById<Button>(R.id.voice).setOnClickListener { voice() }
  findViewById<Button>(R.id.settings).setOnClickListener { settings() }
  findViewById<Button>(R.id.pcTest).setOnClickListener { testPcAgent() }
  tts=TextToSpeech(this) { result ->
   if(result==TextToSpeech.SUCCESS) tts?.setLanguage(Locale.forLanguageTag("bn-BD"))
  }
  refreshStatus()
 }

 private fun refreshStatus() {
  val pc=prefs.getString("pc_url", "").orEmpty()
  status.text = if (pc.isNotBlank())
   "PC Agent: configured • Cloud AI: " + if (prefs.getString("gemini_key", "").orEmpty().isNotBlank()) model else "not configured"
  else if (prefs.getString("gemini_key", "").orEmpty().isNotBlank())
   "Cloud AI: Gemini configured • " + model + " • PC Agent: not configured"
  else "Cloud AI: add Gemini API key • PC Agent optional"
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
  val phone = PhoneAgent.handle(this, prompt)
  if (phone != null && !phone.startsWith("Phone Control চালু নেই")) return phone
  val pc = prefs.getString("pc_url", "").orEmpty().trim()
  if (pc.isNotBlank()) {
   val result = sendPcCommandSync(prompt)
   if (result.startsWith("HTTP 200:")) {
    val body = result.removePrefix("HTTP 200: ")
    return try { org.json.JSONObject(body).optString("response").ifBlank { body } } catch(_:Exception) { body }
   }
  }
  return askGemini(prompt)
 }

 private fun speak(text:String) {
  val clean=text.trim(); if(clean.isEmpty()) return
  val r=tts?.setLanguage(Locale.forLanguageTag("bn-BD")) ?: TextToSpeech.ERROR
  if(r==TextToSpeech.LANG_MISSING_DATA || r==TextToSpeech.LANG_NOT_SUPPORTED) tts?.setLanguage(Locale.US)
  tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "agent_reply")
 }

 private fun sendPcCommandSync(command:String):String {
  return try {
   val base=prefs.getString("pc_url","").orEmpty().trim()
   if(base.isBlank()) return "PC Agent URL not configured"
   val conn=URL(base.trimEnd('/') + "/api/mobile/command").openConnection() as HttpURLConnection
   conn.requestMethod="POST"; conn.connectTimeout=10000; conn.readTimeout=90000
   conn.setRequestProperty("Content-Type","application/json")
   conn.setRequestProperty("X-PC-Agent-Token", pcToken); conn.doOutput=true
   conn.outputStream.use { it.write(org.json.JSONObject().put("command",command).toString().toByteArray(Charsets.UTF_8)) }
   val code=conn.responseCode
   val stream=if(code in 200..299) conn.inputStream else conn.errorStream
   "HTTP " + code + ": " + (stream?.bufferedReader()?.use { it.readText() } ?: "")
  } catch(e:Exception) { "PC Agent error: " + (e.message ?: "unknown error") }
 }

 private fun askGemini(prompt:String):String {
  val key=prefs.getString("gemini_key","").orEmpty()
  if(key.isBlank()) return "Gemini key সেট করা নেই। ⚙ Settings খুলে আপনার নিজের API key দিন।"
  return try {
   val url=URL("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent")
   val conn=url.openConnection() as HttpURLConnection
   conn.requestMethod="POST"; conn.connectTimeout=20000; conn.readTimeout=60000
   conn.setRequestProperty("Content-Type","application/json"); conn.setRequestProperty("x-goog-api-key",key); conn.doOutput=true
   val body=org.json.JSONObject().put("contents", org.json.JSONArray().put(
    org.json.JSONObject().put("parts", org.json.JSONArray().put(org.json.JSONObject().put("text",
     "You are My PC AI Agent. Answer clearly in Bengali or English matching the user. Do not claim you performed PC actions unless connected to the PC agent. User request: " + prompt
    )))
   )).toString()
   conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
   val code=conn.responseCode
   val stream=if(code in 200..299) conn.inputStream else conn.errorStream
   val text=stream?.bufferedReader()?.use { it.readText() } ?: ""
   if(code !in 200..299) return "Cloud AI error (" + code + "). API key/model access check করুন।"
   org.json.JSONObject(text).optJSONArray("candidates")?.optJSONObject(0)?.optJSONObject("content")
    ?.optJSONArray("parts")?.optJSONObject(0)?.optString("text")
    ?.takeIf { it.isNotBlank() } ?: "AI কোনো text response দেয়নি।"
  } catch(e:Exception) { "Cloud AI connection error: " + (e.message ?: "unknown error") }
 }

 private fun testPcAgent() {
  val base=prefs.getString("pc_url", "").orEmpty().trim().ifBlank { "http://127.0.0.1:8765" }
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
  val pc=EditText(this).apply { hint="PC Agent URL (optional)"; setText(prefs.getString("pc_url","").orEmpty().ifBlank { "http://127.0.0.1:8765" }) }
  box.addView(key); box.addView(pc)
  AlertDialog.Builder(this).setTitle("AI Settings")
   .setMessage("Gemini ফোনে সরাসরি কাজ করে। PC Agent optional—PC connected হলে command পাঠানো যাবে.")
   .setView(box).setPositiveButton("Save") { _,_ ->
    prefs.edit().putString("gemini_key",key.text.toString().trim()).putString("pc_url",pc.text.toString().trim()).apply(); refreshStatus()
   }.setNegativeButton("Cancel",null).show()
 }

 private fun voice() {
  if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
   requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),voiceReq); return
  }
  startActivityForResult(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
   putExtra(RecognizerIntent.EXTRA_LANGUAGE,"bn-BD")
   putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
  },voiceReq)
 }

 override fun onActivityResult(r:Int,c:Int,d:Intent?){
  super.onActivityResult(r,c,d)
  if(r==voiceReq && c==RESULT_OK){
   input.setText(d?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?:"")
   send(true)
  }
 }

 override fun onDestroy(){
  tts?.stop(); tts?.shutdown(); super.onDestroy()
 }
}