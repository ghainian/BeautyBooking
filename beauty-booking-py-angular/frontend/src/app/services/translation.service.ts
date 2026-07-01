import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class TranslationService {
    private readonly apiBase = 'http://localhost:8000/api/translations';

    constructor(private readonly http: HttpClient) { }

    getLanguage(language: string): Observable<Record<string, string>> {
        return this.http
            .get<Record<string, string>>(`${this.apiBase}/${language}`)
            .pipe(catchError(() => this.http.get<Record<string, string>>(`${this.apiBase}/da`).pipe(catchError(() => of({})))));
    }
}
