package com.kayum.aiaagent

import android.content.Context
import android.content.Intent
import android.net.Uri

object PhoneAgent {
 fun handle(context: Context, raw: String): String? {
  val p = raw.trim().lowercase()
  val service = AgentAccessibilityService.instance
  if (p == "back" || p.contains("go back") || p.contains("পিছনে যাও")) {
   if (service != null) { service.performGlobalBack(); return "ফোনে Back করা হয়েছে।" }
   return "Phone Control চালু নেই। নিচের Phone Control বাটন থেকে Accessibility Service চালু করুন।"
  }
  if (p == "home" || p.contains("go home") || p.contains("হোমে যাও")) {
   if (service != null) { service.performGlobalHome(); return "ফোনের Home screen খোলা হয়েছে।" }
   return "Phone Control চালু নেই।"
  }
  if (p.contains("recent") || p.contains("recents") || p.contains("recent apps")) {
   if (service != null) { service.performGlobalRecents(); return "Recent Apps খোলা হয়েছে।" }
   return "Phone Control চালু নেই।"
  }
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
  } catch(e: Exception) { "App open failed: " + (e.message ?: "unknown error") }
  val tap = Regex("""(?:tap|click|press|ক্লিক|চাপ)\s+(.+)""", RegexOption.IGNORE_CASE).find(raw)
  if (tap != null) {
   if (service == null) return "Phone Control চালু নেই।"
   val target = tap.groupValues[1].trim()
   return if (service.clickText(target)) "“" + target + "” চাপা হয়েছে।" else "Screen-এ “" + target + "” পাওয়া যায়নি।"
  }
  return null
 }
}
