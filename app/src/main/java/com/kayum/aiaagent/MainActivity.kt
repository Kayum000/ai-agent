package com.kayum.aiaagent
import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognizerIntent
import android.widget.*
import java.util.Locale

class MainActivity : Activity() {
 private lateinit var chat: TextView
 private lateinit var input: EditText
 private val voiceReq=42
 override fun onCreate(b: Bundle?) { super.onCreate(b); setContentView(R.layout.activity_main)
  chat=findViewById(R.id.chat); input=findViewById(R.id.input)
  findViewById<Button>(R.id.send).setOnClickListener { send() }
  findViewById<Button>(R.id.voice).setOnClickListener { voice() }
 }
 private fun send(){ val s=input.text.toString().trim(); if(s.isEmpty())return
  chat.append("\n\nYou: $s\nAgent: Mobile app is ready. Connect your AI backend/PC Agent to receive live AI actions.")
  input.setText("")
 }
 private fun voice(){ if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),voiceReq);return}
  startActivityForResult(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply { putExtra(RecognizerIntent.EXTRA_LANGUAGE, "bn-BD"); putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM) }, voiceReq)
 }
 override fun onActivityResult(r:Int,c:Int,d:Intent?){super.onActivityResult(r,c,d); if(r==voiceReq && c==RESULT_OK){input.setText(d?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?:""); send()}}
}
