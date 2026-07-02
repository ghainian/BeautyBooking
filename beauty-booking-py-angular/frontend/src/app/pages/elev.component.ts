import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'app-elev-page',
    standalone: true,
    templateUrl: './elev.component.html'
})
export class ElevComponent implements OnInit {
    ngOnInit(): void {
        document.body.className = 'contact-page';
        document.title = 'Bestil tid Med FrisørSole Elev';
    }
}
