import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { Subscription } from 'rxjs';

type ChatTurn = {
    role: 'user' | 'agent';
    text: string;
};

const ALLOWED_LANGS = ['da', 'en', 'fr', 'de', 'zh'];

const GREETINGS: Record<string, string> = {
    da: 'Hej. Jeg kan hjælpe med booking, priser, åbningstider og ledige tider.',
    en: 'Hi. I can help with booking, prices, opening hours, and availability.',
    fr: 'Bonjour. Je peux vous aider avec les réservations, les prix, les horaires et les disponibilités.',
    de: 'Hallo. Ich helfe Ihnen gerne bei Buchungen, Preisen, Öffnungszeiten und Verfügbarkeit.',
    zh: '您好。我可以帮助您预约、了解价格、营业时间和可用时段。',
};

const PLACEHOLDERS: Record<string, string> = {
    da: 'Prøv: Bestil dame klip fredag klokken 10, +45 22334455',
    en: 'Try: Book ladies haircut Friday at 10, +45 22334455',
    fr: 'Essayez : Réserver une coupe femme vendredi à 10h, +45 22334455',
    de: 'Versuch: Damenhaarschnitt Freitag um 10 buchen, +45 22334455',
    zh: '试试：预约女士理发周五10点，+45 22334455',
};

const TITLES: Record<string, string> = {
    da: 'Anova Assistent',
    en: 'Anova Assistant',
    fr: 'Anova Assistant',
    de: 'Anova Assistent',
    zh: 'Anova 助手',
};

const SEND_LABELS: Record<string, { send: string; sending: string }> = {
    da: { send: 'Send', sending: 'Sender...' },
    en: { send: 'Send', sending: 'Sending...' },
    fr: { send: 'Envoyer', sending: 'Envoi...' },
    de: { send: 'Senden', sending: 'Sendet...' },
    zh: { send: '发送', sending: '发送中...' },
};

const LAUNCHER_LABELS: Record<string, { open: string; close: string }> = {
    da: { open: 'Chat Med Anova', close: 'Luk Chat' },
    en: { open: 'Chat With Anova', close: 'Close Chat' },
    fr: { open: 'Chatter avec Anova', close: 'Fermer' },
    de: { open: 'Chat mit Anova', close: 'Chat schließen' },
    zh: { open: '与Anova聊天', close: '关闭聊天' },
};

@Component({
    selector: 'app-chat-widget',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './chat-widget.component.html',
    styleUrl: './chat-widget.component.css',
})
export class ChatWidgetComponent implements OnInit, OnDestroy {
    open = false;
    sessionId = '';
    currentMessage = '';
    sending = false;
    placeholder = PLACEHOLDERS['da'];
    title = TITLES['da'];
    sendLabel = SEND_LABELS['da'];
    launcherLabel = LAUNCHER_LABELS['da'];
    messages: ChatTurn[] = [];

    private activeLang = 'da';
    private readonly subs = new Subscription();

    constructor(private readonly http: HttpClient, private readonly router: Router) { }

    ngOnInit(): void {
        // Read the language from the URL on every navigation.
        // Using Router events works from AppComponent-level components that are
        // outside the router outlet, where ActivatedRoute.queryParamMap never fires.
        const sub = this.router.events.pipe(
            filter((e): e is NavigationEnd => e instanceof NavigationEnd)
        ).subscribe((e) => {
            this.activeLang = this.langFromUrl(e.urlAfterRedirects);
            this.applyLanguage();
        });
        this.subs.add(sub);

        // Also apply immediately for the current URL (page load / hard refresh).
        this.activeLang = this.langFromUrl(this.router.url);
        this.applyLanguage();
    }

    private langFromUrl(url: string): string {
        const qs = url.includes('?') ? url.split('?')[1] : '';
        const params = new URLSearchParams(qs);
        const fromUrl = (params.get('culture') || params.get('ui-culture') || '').toLowerCase().slice(0, 2);
        if (ALLOWED_LANGS.includes(fromUrl)) return fromUrl;
        // No URL param: fall back to the session choice (default 'da').
        const saved = sessionStorage.getItem('anovaLang') || 'da';
        return ALLOWED_LANGS.includes(saved) ? saved : 'da';
    }

    ngOnDestroy(): void {
        this.subs.unsubscribe();
    }

    toggleOpen(): void {
        this.open = !this.open;
        if (this.open) {
            this.applyLanguage();
        }
    }

    private applyLanguage(): void {
        const lang = this.activeLang;
        this.placeholder = PLACEHOLDERS[lang] ?? PLACEHOLDERS['da'];
        this.title = TITLES[lang] ?? TITLES['da'];
        this.sendLabel = SEND_LABELS[lang] ?? SEND_LABELS['da'];
        this.launcherLabel = LAUNCHER_LABELS[lang] ?? LAUNCHER_LABELS['da'];
        // Update the greeting only while the conversation hasn't really started.
        if (this.messages.length === 0 || (this.messages.length === 1 && this.messages[0].role === 'agent')) {
            this.messages = [{ role: 'agent', text: GREETINGS[lang] ?? GREETINGS['da'] }];
        }
    }

    sendMessage(): void {
        const text = this.currentMessage.trim();
        if (!text || this.sending) {
            return;
        }

        this.messages.push({ role: 'user', text });
        this.currentMessage = '';
        this.sending = true;

        const language = this.activeLang;
        this.http
            .post<{ session_id: string; reply: string }>('/api/chat', {
                message: text,
                session_id: this.sessionId || null,
                language,
            })
            .subscribe({
                next: (response) => {
                    this.sessionId = response.session_id;
                    this.messages.push({ role: 'agent', text: response.reply });
                    this.sending = false;
                },
                error: () => {
                    this.messages.push({
                        role: 'agent',
                        text: 'There was an error. Please try again in a moment.',
                    });
                    this.sending = false;
                },
            });
    }
}
