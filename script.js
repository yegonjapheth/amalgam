document.addEventListener('DOMContentLoaded', function() {
    const bookSearch = document.getElementById('book-search');
    const categorySelect = document.getElementById('category-select');

    if (bookSearch) {
        bookSearch.addEventListener('input', debounce(function() {
            searchBooks(this.value);
        }, 300));
    }

    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            window.location.href = '/books?category=' + this.value;
        });
    }
});

function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this, args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            func.apply(context, args);
        }, wait);
    };
}

function searchBooks(query) {
    fetch('/search_books?query=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(books => {
            // Update the book list with search results
            const bookList = document.querySelector('table tbody');
            bookList.innerHTML = '';
            books.forEach(book => {
                bookList.innerHTML += `
                    <tr>
                        <td>${book.title}</td>
                        <td>${book.author}</td>
                        <td>${book.book_id}</td>
                        <td>Available</td>
                    </tr>
                `;
            });
        });
}
