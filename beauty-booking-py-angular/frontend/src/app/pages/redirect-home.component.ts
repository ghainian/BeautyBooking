import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
    selector: 'app-redirect-home',
    standalone: true,
    template: ''
})
export class RedirectHomeComponent implements OnInit {
    private readonly allowedLanguages = ['da', 'en', 'fr', 'de', 'zh'];

    constructor(private readonly route: ActivatedRoute, private readonly router: Router) { }

    ngOnInit(): void {
        const fragment = this.route.snapshot.data['fragment'] as string | undefined;
        const requested = (
            this.route.snapshot.queryParamMap.get('culture')
            || this.route.snapshot.queryParamMap.get('ui-culture')
            || localStorage.getItem('anovaLang')
            || 'da'
        ).toLowerCase();
        const language = this.allowedLanguages.includes(requested) ? requested : 'da';
        localStorage.setItem('anovaLang', language);

        this.router.navigate(['/home'], {
            fragment: fragment ?? undefined,
            queryParams: {
                culture: language,
                'ui-culture': language,
            },
            replaceUrl: true
        });
    }
}
