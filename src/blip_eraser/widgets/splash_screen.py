def _load_logo(self, accent: str) -> None:
        if ASSET_LOGO_PATH.exists():
            pixmap = QPixmap(str(ASSET_LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(
                    SPLASH_LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation
                )
                self._logo.setPixmap(scaled)
                self._logo.resize(scaled.size())
                return

        pm = QPixmap(160, 160)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent))
        painter.drawRoundedRect(QRect(10, 10, 140, 140), 32, 32)
        painter.setPen(QColor(255, 255, 255))
        font = QFont(self.font())
        font.setPointSize(64)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "B")
        painter.end()
        self._logo.setPixmap(pm)
        self._logo.resize(pm.size())

    def _layout_hero_positions(self) -> None:
        self._title.adjustSize()

        hero_w = self._hero.width()
        logo_w, logo_h = self._logo.width(), self._logo.height()
        title_w, title_h = self._title.width(), self._title.height()

        logo_y = 0
        title_y = logo_h + 12

        self._logo_end_pos = QPoint((hero_w - logo_w) // 2, logo_y)
        self._title_end_pos = QPoint((hero_w - title_w) // 2, title_y)

        self._logo_start_pos = QPoint(hero_w + 60, logo_y)
        self._title_start_pos = QPoint(hero_w + 40, title_y)

        self._logo.move(self._logo_start_pos)
        self._title.move(self._title_start_pos)

    def _center_on_screen(self) -> None:
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - self.width() // 2,
            geometry.center().y() - self.height() // 2,
        )

    def _setup_video_or_fallback(self) -> None:
        """Intenta configurar video con QVideoSink; si falla, usa fallback de logo animado."""
        self._video_loaded = False

        if not _QMULTIMEDIA_AVAILABLE or not _QVIDEOSINK_AVAILABLE:
            self._video_widget = None
            self._video_sink = None
            self._media_player = None
            return

        try:
            from pathlib import Path

            video_path = Path(ASSET_SPLASH_VIDEO)
            if not video_path.exists():
                return

            # Widget personalizado que pinta frames - OCUPA TODA LA VENTANA
            self._video_widget = _VideoWidget()
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._video_widget.hide()

            # QVideoSink para recibir frames
            self._video_sink = QVideoSink(self)
            self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

            self._media_player = QMediaPlayer(self)
            self._media_player.setVideoSink(self._video_sink)
            self._media_player.setSource(QUrl.fromLocalFile(str(Path(ASSET_SPLASH_VIDEO))))
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._media_player.errorOccurred.connect(self._on_media_error)

            self._video_loaded = True

        except Exception:
            self._video_widget = None
            self._video_sink = None
            self._media_player = None
            self._video_loaded = False

    def _on_video_frame_changed(self, frame) -> None:
        """Callback cuando llega un nuevo frame del QVideoSink."""
        if not frame.isValid() or not self._video_widget:
            return
        # Convertir a QImage para pintar en paintEvent
        image = frame.toImage()
        if not image.isNull():
            try:
                from blip_eraser.utils.log import write_diagnostic
                write_diagnostic(
                    f"SPLASH_FRAME: frame_size={frame.width()}x{frame.height()} "
                    f"image_size={image.width()}x{image.height()} "
                    f"video_widget_size={self._video_widget.width()}x{self._video_widget.height()}"
                )
            except Exception:
                pass
            self._video_widget.set_frame(image)

    def _start_intro(self) -> None:
        if self._video_loaded and self._media_player:
            # Cambiar a página de video
            self._stacked.setCurrentIndex(0)
            self._logo.hide()
            self._title.hide()
            self._video_widget.show()
            self._media_player.play()
        else:
            self._start_fallback_animation()

    def _start_fallback_animation(self) -> None:
        """Animación original: logo+título deslizándose desde la derecha."""
        self._video_widget = None
        self._video_sink = None
        self._media_player = None
        self._video_loaded = False

        self._logo.show()
        self._title.show()

        logo_pos = QPropertyAnimation(self._logo, b"pos", self)
        logo_pos.setDuration(_INTRO_LOGO_MS)
        logo_pos.setEasingCurve(QEasingCurve.Type.OutQuart)
        logo_pos.setStartValue(self._logo_start_pos)
        logo_pos.setEndValue(self._logo_end_pos)

        logo_opacity = QPropertyAnimation(self._logo_effect, b"opacity", self)
        logo_opacity.setDuration(_INTRO_LOGO_MS)
        logo_opacity.setStartValue(0.0)
        logo_opacity.setEndValue(1.0)

        logo_group = QParallelAnimationGroup(self)
        logo_group.addAnimation(logo_pos)
        logo_group.addAnimation(logo_opacity)

        title_pos = QPropertyAnimation(self._title, b"pos", self)
        title_pos.setDuration(_INTRO_TITLE_MS)
        title_pos.setEasingCurve(QEasingCurve.Type.OutQuart)
        title_pos.setStartValue(self._title_start_pos)
        title_pos.setEndValue(self._title_end_pos)

        title_opacity = QPropertyAnimation(self._title_effect, b"opacity", self)
        title_opacity.setDuration(_INTRO_TITLE_MS)
        title_opacity.setStartValue(0.0)
        title_opacity.setEndValue(1.0)

        title_group = QParallelAnimationGroup(self)
        title_group.addAnimation(title_pos)
        title_group.addAnimation(title_opacity)

        delay_bridge = QPropertyAnimation(self._title_effect, b"opacity", self)
        delay_bridge.setDuration(_INTRO_TITLE_DELAY_MS)
        delay_bridge.setStartValue(0.0)
        delay_bridge.setEndValue(0.0)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(logo_group)
        sequence.addAnimation(delay_bridge)
        sequence.addAnimation(title_group)
        sequence.finished.connect(self._on_intro_finished)

        self._intro_anim = sequence
        sequence.start()

    def _on_media_status_changed(self, status) -> None:
        if not self._media_player:
            return

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._video_ended = True
            # Pausar en último frame (no detener)
            self._media_player.pause()
            self._check_both_finished()

    def _on_media_error(self, error, error_string) -> None:
        # Log detallado del error para diagnóstico (codecs faltantes, etc.)
        try:
            from blip_eraser.utils.log import write_diagnostic
            from PyQt6.QtMultimedia import QMediaPlayer
            error_name = QMediaPlayer.Error(error).name if hasattr(QMediaPlayer.Error, '__members__') else str(error)
            write_diagnostic(
                f"SPLASH_MEDIA_ERROR: error={error_name}({error}) "
                f"detail={error_string}"
            )
            # Detectar error típico de codecs faltantes en Linux
            if "shared" in error_string.lower() or "library" in error_string.lower() or "plugin" in error_string.lower() or "decoder" in error_string.lower():
                write_diagnostic(
                    "SPLASH_CODEC_HINT: Probable codecs H.264/AAC faltantes. "
                    "En Arch/CachyOS: sudo pacman -S gst-libav"
                )
        except Exception:
            pass

        # Fallback silencioso a animación original
        self._video_loaded = False
        if self._video_widget:
            self._video_widget.hide()
        if self._media_player:
            self._media_player.stop()
            self._media_player.deleteLater()
            self._media_player = None
        self._video_sink = None
        self._start_fallback_animation()

    def _check_both_finished(self) -> None:
        """Verifica si ambos (video + worker) han terminado para cerrar."""
        if self._video_ended and self._worker_finished:
            self.close()
        elif self._video_ended and not self._worker_finished:
            self._waiting_for_worker = True
        elif self._worker_finished and not self._video_ended:
            self._waiting_for_worker = False
            # El video sigue reproduciéndose; se cerrará en _on_media_status_changed

    def notify_worker_finished(self) -> None:
        """Llamado desde main cuando StartupWorker termina."""
        self._worker_finished = True
        self._check_both_finished()

    def _on_intro_finished(self) -> None:
        self._intro_done = True
        if self._pending_message is not None:
            text, self._pending_message = self._pending_message, None
            self._animate_message(text)

    def set_message(self, text: str) -> None:
        if not self._intro_done:
            self._pending_message = text
            return
        self._animate_message(text)

    def _animate_message(self, text: str) -> None:
        if self._msg_fade_out is not None:
            self._msg_fade_out.stop()
        if self._msg_fade_in is not None:
            self._msg_fade_in.stop()

        if self._video_loaded:
            # MODO VIDEO: usar overlay sobre el video
            self._message_overlay.show()
            self._message_bg.show()
            self._message_overlay.raise_()
            self._message_bg.raise_()
            # Actualizar geometría del fondo semitransparente
            self._message_overlay.adjustSize()
            bg_margin = 12
            self._message_bg.setGeometry(
                self._message_overlay.x() - 12,
                self._message_overlay.y() - 8,
                self._message_overlay.width() + 24,
                self._message_overlay.height() + 16
            )
            self._message_bg.raise_()
            self._message_overlay.raise_()
        else:
            # MODO FALLBACK: mensaje debajo del hero
            self._message.show()
            self._message.raise_()

        if self._msg_fade_out is not None:
            self._msg_fade_out.stop()
        if self._msg_fade_in is not None:
            self._msg_fade_in.stop()

        fade_out = QPropertyAnimation(self._message_effect if not self._video_loaded else self._message_overlay.graphicsEffect(), b"opacity", self)
        fade_out.setDuration(_MSG_FADE_OUT_MS)
        fade_out.setStartValue(self._message_effect.opacity() if not self._video_loaded else self._message_overlay.graphicsEffect().opacity())
        fade_out.setEndValue(0.0)

        def _swap_and_fade_in() -> None:
            if self._video_loaded:
                self._message_overlay.setText(text)
            else:
                self._message.setText(text)
            fade_in = QPropertyAnimation(
                self._message_effect if not self._video_loaded else self._message_overlay.graphicsEffect(),
                b"opacity", self)
            fade_in.setDuration(_MSG_FADE_IN_MS)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            self._msg_fade_in = fade_in
            fade_in.start()

        fade_out.finished.connect(_swap_and_fade_in)
        self._msg_fade_out = fade_out
        fade_out.start()

    def closeEvent(self, event) -> None:
        if self._media_player:
            self._media_player.stop()
        self.closed.emit()
        super().closeEvent(event)