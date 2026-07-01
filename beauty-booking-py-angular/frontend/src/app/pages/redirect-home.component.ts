import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
    selector: 'app-redirect-home',
    standalone: true,
    template: ''
})
export class RedirectHomeComponent implements OnInit {
    constructor(private readonly route: ActivatedRoute, private readonly router: Router) { }

    ngOnInit(): void {
        const fragment = this.route.snapshot.data['fragment'] as string | undefined;
        this.router.navigate(['/home'], { fragment: fragment ?? undefined, replaceUrl: true });
    }
}
