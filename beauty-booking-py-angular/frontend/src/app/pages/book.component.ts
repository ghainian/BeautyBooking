import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'app-book-page',
    standalone: true,
    templateUrl: './book.component.html',
    styleUrl: './book.component.css'
})
export class BookComponent implements OnInit {
    ngOnInit(): void {
        document.body.className = 'contact-page';
        document.title = 'Anova | Bestil tid';
    }
}
