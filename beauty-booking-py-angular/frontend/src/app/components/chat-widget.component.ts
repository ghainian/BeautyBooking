import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type ChatTurn = {
    role: 'user' | 'agent';
    text: string;
};

@Component({
    selector: 'app-chat-widget',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './chat-widget.component.html',
    styleUrl: './chat-widget.component.css',
})
export class ChatWidgetComponent {
    open = false;
    sessionId = '';
    currentMessage = '';
    sending = false;
    messages: ChatTurn[] = [
        {
            role: 'agent',
            text: 'Hi. I can help with booking, prices, opening hours, and availability.',
        },
    ];

    constructor(private readonly http: HttpClient) { }

    toggleOpen(): void {
        this.open = !this.open;
    }

    sendMessage(): void {
        const text = this.currentMessage.trim();
        if (!text || this.sending) {
            return;
        }

        this.messages.push({ role: 'user', text });
        this.currentMessage = '';
        this.sending = true;

        const language = (localStorage.getItem('anovaLang') || 'da').toLowerCase();
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
