package com.kayum.aiaagent

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognizerIntent
import android.widget.*
import android.telephony.SmsManager
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {
 private lateinit var chat: TextView
 private lateinit var input: EditText
 private lateinit var status: TextView
 private val voiceReq=42
 private val smsReq=43
 private val prefs by lazy { getSharedPreferences("agent", MODE_PRIVATE) }
 private val model = "gemini-2.5-flash-lite"
 private val pcToken = "mmc-local-test-token"

 override fun onCreate(b: Bundle?) {
  super.onCreate(b); setContentView(R.layout.activity_main)
  chat=findViewById(R.id.chat); input=findViewById(R.id.input); status=findViewById(R.id.status)
  findViewById<Button>(R.id.send).setOnClickListener { send() }
  findViewById<Button>(R.id.voice).setOnClickListener { voice() }
  findViewById<Button>(R.id.settings).setOnClickListener { settings() }
  findViewById<Button>(R.id.sms).setOnClickListener { smsDialog() }
  findViewById<Button>(R.id.pcTest).setOnClickListener { testPcAgent() }
  refreshStatus()
 }

 private fun refreshStatus() {
  val pc=prefs.getString("pc_url", "").orEmpty()
  status.text = if (pc.isNotBlank())
   "PC Agent: configured • Cloud AI: " + if (prefs.getString("gemini_key", "").orEmpty().isNotBlank()) model else "not configured"
  else if (prefs.getString("gemini_key", "").orEmpty().isNotBlank())
   "Cloud AI: Gemini configured • " + model + " • PC Agent: not configured"
  else "Cloud AI: add Gemini API key • PC Agent: add URL in Settings"
 }

 private fun send() {
  val s=input.text.toString().trim(); if(s.isEmpty()) return
  chat.append("\n\nYou: " + s + "\nAgent: thinking…")
  input.setText("")
  thread {
   val answer = askGemini(s)
   runOnUiThread {
    chat.append("\n" + answer)
    val scroll=findViewById<ScrollView>(R.id.scroll)
    scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
   }
  }
 }

 private fun askGemini(prompt:String):String {
  val key=prefs.getString("gemini_key","").orEmpty()
  if(key.isBlank()) return "Gemini key সেট করা নেই। ⚙ Settings খুলে আপনার নিজের API key দিন।"
  return try {
   val url=URL("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent")
   val conn=url.openConnection() as HttpURLConnection
   conn.requestMethod="POST"; conn.connectTimeout=20000; conn.readTimeout=60000
   conn.setRequestProperty("Content-Type","application/json")
   conn.setRequestProperty("x-goog-api-key",key); conn.doOutput=true
   val body=org.json.JSONObject().put("contents", org.json.JSONArray().put(
    org.json.JSONObject().put("parts", org.json.JSONArray().put(org.json.JSONObject().put("text",
     "You are My PC AI Agent. Answer clearly in Bengali or English matching the user. Do not claim you performed PC actions unless connected to the PC agent. User request: " + prompt
    )))
   )).toString()
   conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
   val stream=if(conn.responseCode in 200..299) conn.inputStream else conn.errorStream
   val text=stream.bufferedReader().use { it.readText() }
   if(conn.responseCode !in 200..299) return "Cloud AI error (" + conn.responseCode + "). API key/model access check করুন।"
   val root=org.json.JSONObject(text)
   root.optJSONArray("candidates")?.optJSONObject(0)?.optJSONObject("content")
    ?.optJSONArray("parts")?.optJSONObject(0)?.optString("text")
    ?.takeIf { it.isNotBlank() } ?: "AI কোনো text response দেয়নি।"
  } catch(e:Exception) { "Cloud AI connection error: " + (e.message ?: "unknown error") }
 }

 private fun testPcAgent() {
  val base=prefs.getString("pc_url", "").orEmpty().trim().ifBlank { "http://127.0.0.1:8765" }
  thread {
   try {
    val url=URL(base.trimEnd('/') + "/health")
    val conn=url.openConnection() as HttpURLConnection
    conn.requestMethod="GET"; conn.connectTimeout=5000; conn.readTimeout=5000
    val code=conn.responseCode
    val body=(if(code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
    runOnUiThread {
     if(code in 200..299) {
      status.text="PC Agent: CONNECTED • testing command…"
      chat.append("\n\nPC Test: CONNECTED\n" + body + "\nCommand Test: sending system info…")
     } else {
      status.text="PC Agent: HTTP " + code
      chat.append("\n\nPC Test: FAILED\nHTTP " + code + "\n" + body)
     }
    }
    if(code in 200..299) {
     sendPcCommand("system info") { result ->
      status.text = if(result.startsWith("HTTP 200:")) "PC Agent: COMMAND OK" else "PC Agent: command failed"
      chat.append("\nCommand Test Result:\n" + result)
     }
    }
   } catch(e:Exception) {
    runOnUiThread {
     status.text="PC Agent: connection failed"
     chat.append("\n\nPC Test: FAILED\n" + (e.message ?: "unknown error"))
    }
   }
  }
 }

 private fun sendPcCommand(command:String, callback:(String)->Unit) {
  val base=prefs.getString("pc_url", "").orEmpty().trim().ifBlank { "http://127.0.0.1:8765" }
  thread {
   val result=try {
    val conn=URL(base.trimEnd('/') + "/api/mobile/command").openConnection() as HttpURLConnection
    conn.requestMethod="POST"; conn.connectTimeout=10000; conn.readTimeout=30000
    conn.setRequestProperty("Content-Type","application/json")
    conn.setRequestProperty("X-PC-Agent-Token", pcToken)
    conn.doOutput=true
    val body=org.json.JSONObject().put("command",command).toString()
    conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
    val code=conn.responseCode
    val stream=if(code in 200..299) conn.inputStream else conn.errorStream
    val text=stream.bufferedReader().use { it.readText() }
    "HTTP " + code + ": " + text
   } catch(e:Exception) { "PC Agent error: " + (e.message ?: "unknown error") }
   runOnUiThread { callback(result) }
  }
 }

 private fun smsDialog() {
  val box=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(40,10,40,10) }
  val phone=EditText(this).apply { hint="Phone number"; inputType=android.text.InputType.TYPE_CLASS_PHONE }
  val msg=EditText(this).apply { hint="SMS message"; minLines=3; gravity=android.view.Gravity.TOP }
  box.addView(phone); box.addView(msg)
  AlertDialog.Builder(this).setTitle("Send SMS").setView(box)
   .setPositiveButton("Send") { _,_ -> sendSms(phone.text.toString().trim(), msg.text.toString()) }
   .setNegativeButton("Cancel",null).show()
 }

 private fun sendSms(phone:String, msg:String) {
  if(phone.isBlank() || msg.isBlank()) { Toast.makeText(this,"Phone number and message required",Toast.LENGTH_SHORT).show(); return }
  if(checkSelfPermission(Manifest.permission.SEND_SMS)!=PackageManager.PERMISSION_GRANTED){ requestPermissions(arrayOf(Manifest.permission.SEND_SMS),smsReq); return }
  try { SmsManager.getDefault().sendTextMessage(phone,null,msg,null,null); Toast.makeText(this,"SMS send requested",Toast.LENGTH_SHORT).show() }
  catch(e:Exception) { Toast.makeText(this,"SMS failed: " + (e.message ?: "unknown error"),Toast.LENGTH_LONG).show() }
 }

 private fun settings() {
  val box=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(40,10,40,10) }
  val key=EditText(this).apply {
   hint="Gemini API key"
   inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
   setText(prefs.getString("gemini_key",""))
  }
  val pc=EditText(this).apply { hint="PC Agent URL"; setText(prefs.getString("pc_url","").orEmpty().ifBlank { "http://127.0.0.1:8765" }) }
  box.addView(key); box.addView(pc)
  AlertDialog.Builder(this).setTitle("AI Settings")
   .setMessage("PC Agent test USB/ADB reverse-এ http://127.0.0.1:8765 ব্যবহার করুন. Wi-Fi হলে PC-এর LAN IP দিন.")
   .setView(box).setPositiveButton("Save") { _,_ ->
    prefs.edit().putString("gemini_key",key.text.toString().trim()).putString("pc_url",pc.text.toString().trim()).apply()
    refreshStatus()
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

 override fun onRequestPermissionsResult(requestCode:Int, permissions:Array<out String>, grantResults:IntArray){
  super.onRequestPermissionsResult(requestCode,permissions,grantResults)
  if(requestCode==smsReq) Toast.makeText(this, if(grantResults.firstOrNull()==PackageManager.PERMISSION_GRANTED) "SMS permission granted. Tap Send SMS again." else "SMS permission denied", Toast.LENGTH_SHORT).show()
 }

 override fun onActivityResult(r:Int,c:Int,d:Intent?){
  super.onActivityResult(r,c,d)
  if(r==voiceReq && c==RESULT_OK){ input.setText(d?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?:""); send() }
 }
}