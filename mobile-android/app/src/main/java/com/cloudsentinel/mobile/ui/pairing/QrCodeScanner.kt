package com.cloudsentinel.mobile.ui.pairing

import android.util.Size
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

@androidx.annotation.OptIn(ExperimentalGetImage::class)
@Composable
fun QrCodeScanner(
    onQrScanned: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val haptic = LocalHapticFeedback.current
    val density = LocalDensity.current
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }
    val scanner = remember { BarcodeScanning.getClient() }

    var camera by remember { mutableStateOf<Camera?>(null) }
    var currentZoom by remember { mutableFloatStateOf(1f) }
    var minZoom by remember { mutableFloatStateOf(1f) }
    var maxZoom by remember { mutableFloatStateOf(4f) }

    var focusPoint by remember { mutableStateOf<Offset?>(null) }
    var focusTrigger by remember { mutableIntStateOf(0) }
    val focusScale = remember { Animatable(1.35f) }
    val focusAlpha = remember { Animatable(0f) }

    LaunchedEffect(focusTrigger) {
        if (focusTrigger > 0 && focusPoint != null) {
            focusScale.snapTo(1.35f)
            focusAlpha.snapTo(1f)
            focusScale.animateTo(1f, animationSpec = tween(180))
            kotlinx.coroutines.delay(550)
            focusAlpha.animateTo(0f, animationSpec = tween(250))
            focusPoint = null
        }
    }

    fun applyZoom(target: Float) {
        val cam = camera ?: return
        val clamped = target.coerceIn(minZoom, maxZoom)
        currentZoom = clamped
        cam.cameraControl.setZoomRatio(clamped)
    }

    DisposableEffect(Unit) {
        onDispose {
            cameraExecutor.shutdown()
            scanner.close()
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                val previewView = PreviewView(ctx)
                val scaleDetector = ScaleGestureDetector(
                    ctx,
                    object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
                        override fun onScale(detector: ScaleGestureDetector): Boolean {
                            val zoomState = camera?.cameraInfo?.zoomState?.value
                            val min = zoomState?.minZoomRatio ?: minZoom
                            val max = zoomState?.maxZoomRatio ?: maxZoom
                            val next = ((zoomState?.zoomRatio ?: currentZoom) * detector.scaleFactor)
                                .coerceIn(min, max)
                            currentZoom = next
                            camera?.cameraControl?.setZoomRatio(next)
                            return true
                        }
                    }
                )
                val tapDetector = GestureDetector(
                    ctx,
                    object : GestureDetector.SimpleOnGestureListener() {
                        override fun onSingleTapConfirmed(e: MotionEvent): Boolean {
                            val cam = camera ?: return false
                            val point = previewView.meteringPointFactory.createPoint(e.x, e.y)
                            val action = FocusMeteringAction.Builder(
                                point,
                                FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
                            )
                                .setAutoCancelDuration(3, TimeUnit.SECONDS)
                                .build()
                            cam.cameraControl.startFocusAndMetering(action)
                            focusPoint = Offset(e.x, e.y)
                            focusTrigger++
                            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            return true
                        }
                    }
                )
                previewView.setOnTouchListener { _, event ->
                    scaleDetector.onTouchEvent(event)
                    tapDetector.onTouchEvent(event)
                    true
                }

                val providerFuture = ProcessCameraProvider.getInstance(ctx)
                providerFuture.addListener({
                    val cameraProvider = providerFuture.get()
                    val preview = Preview.Builder().build().also {
                        it.surfaceProvider = previewView.surfaceProvider
                    }
                    val analysis = ImageAnalysis.Builder()
                        .setTargetResolution(Size(1280, 720))
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()

                    analysis.setAnalyzer(cameraExecutor) { imageProxy ->
                        val mediaImage = imageProxy.image
                        if (mediaImage != null) {
                            val inputImage = InputImage.fromMediaImage(
                                mediaImage,
                                imageProxy.imageInfo.rotationDegrees
                            )
                            scanner.process(inputImage)
                                .addOnSuccessListener { barcodes ->
                                    val raw = barcodes.firstOrNull()?.rawValue
                                    if (!raw.isNullOrBlank()) {
                                        onQrScanned(raw)
                                    }
                                }
                                .addOnCompleteListener {
                                    imageProxy.close()
                                }
                        } else {
                            imageProxy.close()
                        }
                    }

                    runCatching {
                        cameraProvider.unbindAll()
                        val bound = cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            analysis
                        )
                        camera = bound
                        bound.cameraInfo.zoomState.value?.let { zs ->
                            minZoom = zs.minZoomRatio
                            maxZoom = zs.maxZoomRatio
                            currentZoom = zs.zoomRatio
                        }
                    }
                }, ctx.mainExecutor)
                previewView
            }
        )

        // Touch-to-Focus animated reticle
        focusPoint?.let { pt ->
            val reticleSizePx = with(density) { 58.dp.toPx() }
            Box(
                modifier = Modifier
                    .offset {
                        IntOffset(
                            (pt.x - reticleSizePx / 2f).roundToInt(),
                            (pt.y - reticleSizePx / 2f).roundToInt()
                        )
                    }
                    .size(58.dp)
                    .scale(focusScale.value)
                    .alpha(focusAlpha.value)
                    .border(1.8.dp, ElectricBlueSoft, CircleShape)
                    .padding(6.dp)
            ) {
                Box(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(ElectricBlueSoft.copy(alpha = 0.85f))
                )
            }
        }

        // Minimalist Zoom In / Out Controls (bottom-center)
        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 14.dp)
                .clip(RoundedCornerShape(50))
                .background(Color.Black.copy(alpha = 0.65f))
                .padding(horizontal = 6.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .clickable {
                        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        applyZoom(currentZoom - 0.5f)
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Remove,
                    contentDescription = "Zoom out",
                    tint = Color.White,
                    modifier = Modifier.size(16.dp)
                )
            }

            Text(
                text = String.format(Locale.US, "%.1fx", currentZoom),
                style = MaterialTheme.typography.labelMedium.copy(
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.SemiBold
                ),
                color = Color.White,
                fontSize = 12.sp,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable {
                        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        applyZoom(1f)
                    }
                    .padding(horizontal = 6.dp, vertical = 4.dp)
            )

            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .clickable {
                        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        applyZoom(currentZoom + 0.5f)
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "Zoom in",
                    tint = Color.White,
                    modifier = Modifier.size(16.dp)
                )
            }
        }
    }
}
