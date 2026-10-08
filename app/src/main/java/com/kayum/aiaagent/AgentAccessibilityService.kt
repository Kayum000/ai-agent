package com.kayum.aiaagent

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent

class AgentAccessibilityService : AccessibilityService() {
 companion object { var instance: AgentAccessibilityService? = null }
 override fun onServiceConnected() {
  super.onServiceConnected(); instance = this
  serviceInfo = AccessibilityServiceInfo().apply {
   eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
   feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
   flags = AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
  }
 }
 override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
 override fun onInterrupt() {}
 override fun onDestroy() { if (instance === this) instance = null; super.onDestroy() }
 fun performGlobalBack() { performGlobalAction(GLOBAL_ACTION_BACK) }
 fun performGlobalHome() { performGlobalAction(GLOBAL_ACTION_HOME) }
 fun performGlobalRecents() { performGlobalAction(GLOBAL_ACTION_RECENTS) }
 fun clickText(target: String): Boolean {
  val root = rootInActiveWindow ?: return false
  val node = findText(root, target) ?: return false
  if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
  val parent = node.parent
  if (parent != null && parent.isClickable) return parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
  val r = Rect(); node.getBoundsInScreen(r)
  if (r.width() > 0 && r.height() > 0) {
   val path = android.graphics.Path().apply { moveTo(r.centerX().toFloat(), r.centerY().toFloat()) }
   val gesture = android.accessibilityservice.GestureDescription.Builder()
    .addStroke(android.accessibilityservice.GestureDescription.StrokeDescription(path, 0, 80)).build()
   return dispatchGesture(gesture, null, Handler(Looper.getMainLooper()))
  }
  return false
 }
 private fun findText(node: AccessibilityNodeInfo, target: String): AccessibilityNodeInfo? {
  val t = node.text?.toString().orEmpty(); val d = node.contentDescription?.toString().orEmpty()
  if (t.equals(target, true) || d.equals(target, true) || t.contains(target, true) || d.contains(target, true)) return node
  for (i in 0 until node.childCount) {
   val found = node.getChild(i)?.let { findText(it, target) }
   if (found != null) return found
  }
  return null
 }
}
