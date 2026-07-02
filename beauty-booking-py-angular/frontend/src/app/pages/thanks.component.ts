import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'app-thanks-page',
    standalone: true,
    templateUrl: './thanks.component.html'
})
export class ThanksComponent implements OnInit {
    ngOnInit(): void {
        document.body.className = 'contact-page';
        document.title = 'Anova | Tak for din booking';
    }
}
