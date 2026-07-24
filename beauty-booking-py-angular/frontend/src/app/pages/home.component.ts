import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';
import { TranslationService } from '../services/translation.service';

@Component({
    selector: 'app-home-page',
    standalone: true,
    templateUrl: './home.component.html'
})
export class HomeComponent implements OnInit, OnDestroy {
    private readonly subscriptions = new Subscription();
    private readonly allowedLanguages = ['da', 'en', 'fr', 'de', 'zh'];
    currentLanguage = 'da';
    dict: Record<string, string> = {};

    constructor(private readonly route: ActivatedRoute, private readonly translationService: TranslationService) { }

    ngOnInit(): void {
        document.body.className = 'onepage-home';

        const qpSub = this.route.queryParamMap.subscribe((params) => {
            const fromUrl = (params.get('culture') || params.get('ui-culture') || '').toLowerCase();
            if (this.allowedLanguages.includes(fromUrl)) {
                // User explicitly navigated to a language URL — honour it and remember for this session.
                this.currentLanguage = fromUrl;
                sessionStorage.setItem('anovaLang', fromUrl);
            } else {
                // No URL param: use this session's saved choice, defaulting to Danish.
                // sessionStorage is cleared when the browser tab/window is closed, so
                // every fresh browser session starts in Danish regardless of history.
                const saved = sessionStorage.getItem('anovaLang') || 'da';
                this.currentLanguage = this.allowedLanguages.includes(saved) ? saved : 'da';
            }
            localStorage.setItem('anovaLang', this.currentLanguage);
            this.loadTranslations(this.currentLanguage);
        });

        this.subscriptions.add(qpSub);
    }

    ngOnDestroy(): void {
        this.subscriptions.unsubscribe();
    }

    T(key: string): string {
        return this.dict[key] || key;
    }

    private loadTranslations(lang: string): void {
        const sub = this.translationService.getLanguage(lang).subscribe((data) => {
            this.dict = data;
            document.documentElement.lang = this.currentLanguage;
            document.title = this.T('MetaTitle');
        });

        this.subscriptions.add(sub);
    }
}
