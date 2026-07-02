import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'app-book-page',
    standalone: true,
    templateUrl: './book.component.html'
})
export class BookComponent implements OnInit {
    ngOnInit(): void {
        document.body.className = 'contact-page';
        document.title = 'Anova | Bestil tid';
    }
}
