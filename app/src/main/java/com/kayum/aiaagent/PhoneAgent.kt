package com.kayum.aiaagent

import android.content.Context
import android.content.Intent
import android.net.Uri

object PhoneAgent {
 fun handle(context: Context, raw: String): String? {
  val p = raw.trim().lowercase()

  val urlMatch = Regex("""(?:open|visit|go to|খুলো|খুলে দাও)\s+(https?://\S+)""", RegexOption.IGNORE_CASE).find(raw)
  if (urlMatch != null) {
   context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(urlMatch.groupValues[1])))
   return "Website খোলা হয়েছে।"
  }

  val app = when {
   p.contains("chrome") -> "com.android.chrome"
   p.contains("youtube") -> "com.google.android.youtube"
   p.contains("whatsapp") -> "com.whatsapp"
   p.contains("telegram") -> "org.telegram.messenger"
   p.contains("facebook") -> "com.facebook.katana"
   p.contains("settings") || p.contains("সেটিং") -> "com.android.settings"
   p.contains("play store") -> "com.android.vending"
   else -> null
  }

  if (app != null) return try {
   val intent = context.packageManager.getLaunchIntentForPackage(app)
   if (intent == null) "এই app ফোনে install নেই।" else {
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(intent)
    "App খোলা হয়েছে।"
   }
  } catch(e: Exception) {
   "App open failed: " + (e.message ?: "unknown error")
  }

  return null
 }
}