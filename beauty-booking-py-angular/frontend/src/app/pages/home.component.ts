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
    currentLanguage = 'da';
    dict: Record<string, string> = {};

    constructor(private readonly route: ActivatedRoute, private readonly translationService: TranslationService) { }

    ngOnInit(): void {
        document.body.className = 'onepage-home';

        const qpSub = this.route.queryParamMap.subscribe((params) => {
            const requested = (params.get('culture') || params.get('ui-culture') || 'da').toLowerCase();
            const allowed = ['da', 'en', 'fr', 'de', 'zh'];
            this.currentLanguage = allowed.includes(requested) ? requested : 'da';
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
