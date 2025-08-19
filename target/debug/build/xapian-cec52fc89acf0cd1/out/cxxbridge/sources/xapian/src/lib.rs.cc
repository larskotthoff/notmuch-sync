#include "xapian/xapian-bind.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <memory>
#include <new>
#include <string>
#include <type_traits>
#include <utility>
#if __cplusplus >= 201703L
#include <string_view>
#endif

namespace rust {
inline namespace cxxbridge1 {
// #include "rust/cxx.h"

struct unsafe_bitcopy_t;

namespace {
template <typename T>
class impl;
} // namespace

#ifndef CXXBRIDGE1_RUST_STRING
#define CXXBRIDGE1_RUST_STRING
class String final {
public:
  String() noexcept;
  String(const String &) noexcept;
  String(String &&) noexcept;
  ~String() noexcept;

  String(const std::string &);
  String(const char *);
  String(const char *, std::size_t);
  String(const char16_t *);
  String(const char16_t *, std::size_t);
#ifdef __cpp_char8_t
  String(const char8_t *s);
  String(const char8_t *s, std::size_t len);
#endif

  static String lossy(const std::string &) noexcept;
  static String lossy(const char *) noexcept;
  static String lossy(const char *, std::size_t) noexcept;
  static String lossy(const char16_t *) noexcept;
  static String lossy(const char16_t *, std::size_t) noexcept;

  String &operator=(const String &) & noexcept;
  String &operator=(String &&) & noexcept;

  explicit operator std::string() const;

  const char *data() const noexcept;
  std::size_t size() const noexcept;
  std::size_t length() const noexcept;
  bool empty() const noexcept;

  const char *c_str() noexcept;

  std::size_t capacity() const noexcept;
  void reserve(size_t new_cap) noexcept;

  using iterator = char *;
  iterator begin() noexcept;
  iterator end() noexcept;

  using const_iterator = const char *;
  const_iterator begin() const noexcept;
  const_iterator end() const noexcept;
  const_iterator cbegin() const noexcept;
  const_iterator cend() const noexcept;

  bool operator==(const String &) const noexcept;
  bool operator!=(const String &) const noexcept;
  bool operator<(const String &) const noexcept;
  bool operator<=(const String &) const noexcept;
  bool operator>(const String &) const noexcept;
  bool operator>=(const String &) const noexcept;

  void swap(String &) noexcept;

  String(unsafe_bitcopy_t, const String &) noexcept;

private:
  struct lossy_t;
  String(lossy_t, const char *, std::size_t) noexcept;
  String(lossy_t, const char16_t *, std::size_t) noexcept;
  friend void swap(String &lhs, String &rhs) noexcept { lhs.swap(rhs); }

  std::array<std::uintptr_t, 3> repr;
};
#endif // CXXBRIDGE1_RUST_STRING

#ifndef CXXBRIDGE1_RUST_STR
#define CXXBRIDGE1_RUST_STR
class Str final {
public:
  Str() noexcept;
  Str(const String &) noexcept;
  Str(const std::string &);
  Str(const char *);
  Str(const char *, std::size_t);

  Str &operator=(const Str &) & noexcept = default;

  explicit operator std::string() const;
#if __cplusplus >= 201703L
  explicit operator std::string_view() const;
#endif

  const char *data() const noexcept;
  std::size_t size() const noexcept;
  std::size_t length() const noexcept;
  bool empty() const noexcept;

  Str(const Str &) noexcept = default;
  ~Str() noexcept = default;

  using iterator = const char *;
  using const_iterator = const char *;
  const_iterator begin() const noexcept;
  const_iterator end() const noexcept;
  const_iterator cbegin() const noexcept;
  const_iterator cend() const noexcept;

  bool operator==(const Str &) const noexcept;
  bool operator!=(const Str &) const noexcept;
  bool operator<(const Str &) const noexcept;
  bool operator<=(const Str &) const noexcept;
  bool operator>(const Str &) const noexcept;
  bool operator>=(const Str &) const noexcept;

  void swap(Str &) noexcept;

private:
  class uninit;
  Str(uninit) noexcept;
  friend impl<Str>;

  std::array<std::uintptr_t, 2> repr;
};
#endif // CXXBRIDGE1_RUST_STR

#ifndef CXXBRIDGE1_IS_COMPLETE
#define CXXBRIDGE1_IS_COMPLETE
namespace detail {
namespace {
template <typename T, typename = std::size_t>
struct is_complete : std::false_type {};
template <typename T>
struct is_complete<T, decltype(sizeof(T))> : std::true_type {};
} // namespace
} // namespace detail
#endif // CXXBRIDGE1_IS_COMPLETE

namespace repr {
using Fat = ::std::array<::std::uintptr_t, 2>;

struct PtrLen final {
  void *ptr;
  ::std::size_t len;
};
} // namespace repr

namespace detail {
class Fail final {
  ::rust::repr::PtrLen &throw$;
public:
  Fail(::rust::repr::PtrLen &throw$) noexcept : throw$(throw$) {}
  void operator()(char const *) noexcept;
  void operator()(std::string const &) noexcept;
};
} // namespace detail

namespace {
template <>
class impl<Str> final {
public:
  static repr::Fat repr(Str str) noexcept {
    return str.repr;
  }
};

template <bool> struct deleter_if {
  template <typename T> void operator()(T *) {}
};

template <> struct deleter_if<true> {
  template <typename T> void operator()(T *ptr) { ptr->~T(); }
};
} // namespace
} // namespace cxxbridge1

namespace behavior {
class missing {};
missing trycatch(...);

template <typename Try, typename Fail>
static typename ::std::enable_if<
    ::std::is_same<decltype(trycatch(::std::declval<Try>(), ::std::declval<Fail>())),
                 missing>::value>::type
trycatch(Try &&func, Fail &&fail) noexcept try {
  func();
} catch (::std::exception const &e) {
  fail(e.what());
}
} // namespace behavior
} // namespace rust

namespace Xapian {
  using Database = ::Xapian::Database;
  using Stem = ::Xapian::Stem;
  using WritableDatabase = ::Xapian::WritableDatabase;
  using TermGenerator = ::Xapian::TermGenerator;
  using Document = ::Xapian::Document;
  using MSet = ::Xapian::MSet;
  using MSetIterator = ::Xapian::MSetIterator;
  using TermIterator = ::Xapian::TermIterator;
  using Enquire = ::Xapian::Enquire;
  using QueryParser = ::Xapian::QueryParser;
  using Query = ::Xapian::Query;
  using MultiValueKeyMaker = ::Xapian::MultiValueKeyMaker;
  using RangeProcessor = ::Xapian::RangeProcessor;
  using NumberRangeProcessor = ::Xapian::NumberRangeProcessor;
  using MatchSpy = ::Xapian::MatchSpy;
  using ValueCountMatchSpy = ::Xapian::ValueCountMatchSpy;
  using BoolWeight = ::Xapian::BoolWeight;
  using BM25Weight = ::Xapian::BM25Weight;
}

extern "C" {
::rust::repr::Fat cxxbridge1$version_string() noexcept {
  ::rust::Str (*version_string$)() = ::version_string;
  return ::rust::impl<::rust::Str>::repr(version_string$());
}

::rust::repr::PtrLen cxxbridge1$new_database(::Xapian::Database **return$) noexcept {
  ::std::unique_ptr<::Xapian::Database> (*new_database$)() = ::new_database;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Database *(new_database$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_database_with_path(::rust::Str path, ::std::int32_t db_type, ::Xapian::Database **return$) noexcept {
  ::std::unique_ptr<::Xapian::Database> (*new_database_with_path$)(::rust::Str, ::std::int32_t) = ::new_database_with_path;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Database *(new_database_with_path$(path, db_type).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$database_reopen(::Xapian::Database &db) noexcept {
  void (*database_reopen$)(::Xapian::Database &) = ::database_reopen;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        database_reopen$(db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$database_close(::Xapian::Database &db) noexcept {
  void (*database_close$)(::Xapian::Database &) = ::database_close;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        database_close$(db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_enquire(::Xapian::Database &db, ::Xapian::Enquire **return$) noexcept {
  ::std::unique_ptr<::Xapian::Enquire> (*new_enquire$)(::Xapian::Database &) = ::new_enquire;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Enquire *(new_enquire$(db).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_database(::Xapian::Database &db, ::Xapian::Database &add_db) noexcept {
  void (*add_database$)(::Xapian::Database &, ::Xapian::Database &) = ::add_database;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_database$(db, add_db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_stem(::rust::Str lang, ::Xapian::Stem **return$) noexcept {
  ::std::unique_ptr<::Xapian::Stem> (*new_stem$)(::rust::Str) = ::new_stem;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Stem *(new_stem$(lang).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_writable_database_with_path(::rust::Str path, ::std::int32_t action, ::std::int32_t db_type, ::Xapian::WritableDatabase **return$) noexcept {
  ::std::unique_ptr<::Xapian::WritableDatabase> (*new_writable_database_with_path$)(::rust::Str, ::std::int32_t, ::std::int32_t) = ::new_writable_database_with_path;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::WritableDatabase *(new_writable_database_with_path$(path, action, db_type).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$commit(::Xapian::WritableDatabase &db) noexcept {
  void (*commit$)(::Xapian::WritableDatabase &) = ::commit;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        commit$(db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$close(::Xapian::WritableDatabase &db) noexcept {
  void (*close$)(::Xapian::WritableDatabase &) = ::close;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        close$(db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$replace_document(::Xapian::WritableDatabase &db, ::rust::Str unique_term, ::Xapian::Document &doc, ::std::uint32_t *return$) noexcept {
  ::std::uint32_t (*replace_document$)(::Xapian::WritableDatabase &, ::rust::Str, ::Xapian::Document &) = ::replace_document;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::std::uint32_t(replace_document$(db, unique_term, doc));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$delete_document(::Xapian::WritableDatabase &db, ::rust::Str unique_term) noexcept {
  void (*delete_document$)(::Xapian::WritableDatabase &, ::rust::Str) = ::delete_document;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        delete_document$(db, unique_term);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$get_doccount(::Xapian::WritableDatabase &db, ::std::size_t *return$) noexcept {
  ::std::size_t (*get_doccount$)(::Xapian::WritableDatabase &) = ::get_doccount;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::std::size_t(get_doccount$(db));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_termgenerator(::Xapian::TermGenerator **return$) noexcept {
  ::std::unique_ptr<::Xapian::TermGenerator> (*new_termgenerator$)() = ::new_termgenerator;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::TermGenerator *(new_termgenerator$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_stemmer(::Xapian::TermGenerator &tg, ::Xapian::Stem &stem) noexcept {
  void (*set_stemmer$)(::Xapian::TermGenerator &, ::Xapian::Stem &) = ::set_stemmer;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_stemmer$(tg, stem);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_flags(::Xapian::TermGenerator &tg, ::std::int32_t toggle, ::std::int32_t mask) noexcept {
  void (*set_flags$)(::Xapian::TermGenerator &, ::std::int32_t, ::std::int32_t) = ::set_flags;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_flags$(tg, toggle, mask);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_document(::Xapian::TermGenerator &tg, ::Xapian::Document &doc) noexcept {
  void (*set_document$)(::Xapian::TermGenerator &, ::Xapian::Document &) = ::set_document;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_document$(tg, doc);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_text_with_prefix(::Xapian::TermGenerator &tg, ::rust::Str data, ::rust::Str prefix) noexcept {
  void (*index_text_with_prefix$)(::Xapian::TermGenerator &, ::rust::Str, ::rust::Str) = ::index_text_with_prefix;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_text_with_prefix$(tg, data, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_text(::Xapian::TermGenerator &tg, ::rust::Str data) noexcept {
  void (*index_text$)(::Xapian::TermGenerator &, ::rust::Str) = ::index_text;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_text$(tg, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_int(::Xapian::TermGenerator &tg, ::std::int32_t data, ::rust::Str prefix) noexcept {
  void (*index_int$)(::Xapian::TermGenerator &, ::std::int32_t, ::rust::Str) = ::index_int;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_int$(tg, data, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_long(::Xapian::TermGenerator &tg, ::std::int64_t data, ::rust::Str prefix) noexcept {
  void (*index_long$)(::Xapian::TermGenerator &, ::std::int64_t, ::rust::Str) = ::index_long;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_long$(tg, data, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_float(::Xapian::TermGenerator &tg, float data, ::rust::Str prefix) noexcept {
  void (*index_float$)(::Xapian::TermGenerator &, float, ::rust::Str) = ::index_float;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_float$(tg, data, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$index_double(::Xapian::TermGenerator &tg, double data, ::rust::Str prefix) noexcept {
  void (*index_double$)(::Xapian::TermGenerator &, double, ::rust::Str) = ::index_double;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        index_double$(tg, data, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_document(::Xapian::Document **return$) noexcept {
  ::std::unique_ptr<::Xapian::Document> (*new_document$)() = ::new_document;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Document *(new_document$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_string(::Xapian::Document &doc, ::std::uint32_t slot, ::rust::Str data) noexcept {
  void (*add_string$)(::Xapian::Document &, ::std::uint32_t, ::rust::Str) = ::add_string;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_string$(doc, slot, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_int(::Xapian::Document &doc, ::std::uint32_t slot, ::std::int32_t data) noexcept {
  void (*add_int$)(::Xapian::Document &, ::std::uint32_t, ::std::int32_t) = ::add_int;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_int$(doc, slot, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_long(::Xapian::Document &doc, ::std::uint32_t slot, ::std::int64_t data) noexcept {
  void (*add_long$)(::Xapian::Document &, ::std::uint32_t, ::std::int64_t) = ::add_long;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_long$(doc, slot, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_double(::Xapian::Document &doc, ::std::uint32_t slot, double data) noexcept {
  void (*add_double$)(::Xapian::Document &, ::std::uint32_t, double) = ::add_double;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_double$(doc, slot, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_data(::Xapian::Document &doc, ::rust::Str data) noexcept {
  void (*set_data$)(::Xapian::Document &, ::rust::Str) = ::set_data;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_data$(doc, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$get_doc_data(::Xapian::Document &doc, ::rust::String *return$) noexcept {
  ::rust::String (*get_doc_data$)(::Xapian::Document &) = ::get_doc_data;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::rust::String(get_doc_data$(doc));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_boolean_term(::Xapian::Document &doc, ::rust::Str data) noexcept {
  void (*add_boolean_term$)(::Xapian::Document &, ::rust::Str) = ::add_boolean_term;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_boolean_term$(doc, data);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$get_matches_estimated(::Xapian::MSet &set, ::std::int32_t *return$) noexcept {
  ::std::int32_t (*get_matches_estimated$)(::Xapian::MSet &) = ::get_matches_estimated;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::std::int32_t(get_matches_estimated$(set));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_size(::Xapian::MSet &set, ::std::int32_t *return$) noexcept {
  ::std::int32_t (*mset_size$)(::Xapian::MSet &) = ::mset_size;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::std::int32_t(mset_size$(set));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

void cxxbridge1$mset_snippet(::Xapian::MSet &set, ::rust::Str text, ::std::int32_t length, ::Xapian::Stem &stem, ::std::int32_t flags, ::rust::Str hi_start, ::rust::Str hi_end, ::rust::Str omit, ::rust::String *return$) noexcept {
  ::rust::String (*mset_snippet$)(::Xapian::MSet &, ::rust::Str, ::std::int32_t, ::Xapian::Stem &, ::std::int32_t, ::rust::Str, ::rust::Str, ::rust::Str) = ::mset_snippet;
  new (return$) ::rust::String(mset_snippet$(set, text, length, stem, flags, hi_start, hi_end, omit));
}

::rust::repr::PtrLen cxxbridge1$mset_iterator_get_document(::Xapian::MSetIterator &iter, ::Xapian::Document **return$) noexcept {
  ::std::unique_ptr<::Xapian::Document> (*mset_iterator_get_document$)(::Xapian::MSetIterator &) = ::mset_iterator_get_document;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Document *(mset_iterator_get_document$(iter).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_iterator_eq(::Xapian::MSetIterator &iter, ::Xapian::MSetIterator &other, bool *return$) noexcept {
  bool (*mset_iterator_eq$)(::Xapian::MSetIterator &, ::Xapian::MSetIterator &) = ::mset_iterator_eq;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) bool(mset_iterator_eq$(iter, other));
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_iterator_next(::Xapian::MSetIterator &iter) noexcept {
  void (*mset_iterator_next$)(::Xapian::MSetIterator &) = ::mset_iterator_next;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        mset_iterator_next$(iter);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_begin(::Xapian::MSet &set, ::Xapian::MSetIterator **return$) noexcept {
  ::std::unique_ptr<::Xapian::MSetIterator> (*mset_begin$)(::Xapian::MSet &) = ::mset_begin;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::MSetIterator *(mset_begin$(set).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_end(::Xapian::MSet &set, ::Xapian::MSetIterator **return$) noexcept {
  ::std::unique_ptr<::Xapian::MSetIterator> (*mset_end$)(::Xapian::MSet &) = ::mset_end;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::MSetIterator *(mset_end$(set).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$mset_back(::Xapian::MSet &set, ::Xapian::MSetIterator **return$) noexcept {
  ::std::unique_ptr<::Xapian::MSetIterator> (*mset_back$)(::Xapian::MSet &) = ::mset_back;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::MSetIterator *(mset_back$(set).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$get_mset(::Xapian::Enquire &en, ::std::int32_t from, ::std::int32_t size, ::Xapian::MSet **return$) noexcept {
  ::std::unique_ptr<::Xapian::MSet> (*get_mset$)(::Xapian::Enquire &, ::std::int32_t, ::std::int32_t) = ::get_mset;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::MSet *(get_mset$(en, from, size).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_query(::Xapian::Enquire &en, ::Xapian::Query &query) noexcept {
  void (*set_query$)(::Xapian::Enquire &, ::Xapian::Query &) = ::set_query;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_query$(en, query);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_sort_by_key(::Xapian::Enquire &en, ::Xapian::MultiValueKeyMaker &sorter, bool reverse) noexcept {
  void (*set_sort_by_key$)(::Xapian::Enquire &, ::Xapian::MultiValueKeyMaker &, bool) = ::set_sort_by_key;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_sort_by_key$(en, sorter, reverse);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_matchspy_value_count(::Xapian::Enquire &en, ::Xapian::ValueCountMatchSpy &vcms) noexcept {
  void (*add_matchspy_value_count$)(::Xapian::Enquire &, ::Xapian::ValueCountMatchSpy &) = ::add_matchspy_value_count;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_matchspy_value_count$(en, vcms);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_weighting_scheme_bool(::Xapian::Enquire &en, ::Xapian::BoolWeight &bw) noexcept {
  void (*enquire_set_weighting_scheme_bool$)(::Xapian::Enquire &, ::Xapian::BoolWeight &) = ::enquire_set_weighting_scheme_bool;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_weighting_scheme_bool$(en, bw);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_weighting_scheme_bm25(::Xapian::Enquire &en, ::Xapian::BM25Weight &bw) noexcept {
  void (*enquire_set_weighting_scheme_bm25$)(::Xapian::Enquire &, ::Xapian::BM25Weight &) = ::enquire_set_weighting_scheme_bm25;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_weighting_scheme_bm25$(en, bw);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_docid_order(::Xapian::Enquire &en, ::std::int32_t order) noexcept {
  void (*enquire_set_docid_order$)(::Xapian::Enquire &, ::std::int32_t) = ::enquire_set_docid_order;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_docid_order$(en, order);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_sort_by_relevance(::Xapian::Enquire &en) noexcept {
  void (*enquire_set_sort_by_relevance$)(::Xapian::Enquire &) = ::enquire_set_sort_by_relevance;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_sort_by_relevance$(en);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_sort_by_value(::Xapian::Enquire &en, ::std::uint32_t sort_key, bool reverse) noexcept {
  void (*enquire_set_sort_by_value$)(::Xapian::Enquire &, ::std::uint32_t, bool) = ::enquire_set_sort_by_value;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_sort_by_value$(en, sort_key, reverse);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_sort_by_relevance_then_value(::Xapian::Enquire &en, ::std::uint32_t sort_key, bool reverse) noexcept {
  void (*enquire_set_sort_by_relevance_then_value$)(::Xapian::Enquire &, ::std::uint32_t, bool) = ::enquire_set_sort_by_relevance_then_value;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_sort_by_relevance_then_value$(en, sort_key, reverse);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$enquire_set_collapse_key(::Xapian::Enquire &en, ::std::uint32_t collapse_key, ::std::uint32_t collapse_max) noexcept {
  void (*enquire_set_collapse_key$)(::Xapian::Enquire &, ::std::uint32_t, ::std::uint32_t) = ::enquire_set_collapse_key;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        enquire_set_collapse_key$(en, collapse_key, collapse_max);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_query_parser(::Xapian::QueryParser **return$) noexcept {
  ::std::unique_ptr<::Xapian::QueryParser> (*new_query_parser$)() = ::new_query_parser;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::QueryParser *(new_query_parser$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_max_wildcard_expansion(::Xapian::QueryParser &qp, ::std::int32_t limit) noexcept {
  void (*set_max_wildcard_expansion$)(::Xapian::QueryParser &, ::std::int32_t) = ::set_max_wildcard_expansion;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_max_wildcard_expansion$(qp, limit);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_stemmer_to_qp(::Xapian::QueryParser &qp, ::Xapian::Stem &stem) noexcept {
  void (*set_stemmer_to_qp$)(::Xapian::QueryParser &, ::Xapian::Stem &) = ::set_stemmer_to_qp;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_stemmer_to_qp$(qp, stem);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$set_database(::Xapian::QueryParser &qp, ::Xapian::Database &add_db) noexcept {
  void (*set_database$)(::Xapian::QueryParser &, ::Xapian::Database &) = ::set_database;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        set_database$(qp, add_db);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_prefix(::Xapian::QueryParser &qp, ::rust::Str field, ::rust::Str prefix) noexcept {
  void (*add_prefix$)(::Xapian::QueryParser &, ::rust::Str, ::rust::Str) = ::add_prefix;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_prefix$(qp, field, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_boolean_prefix(::Xapian::QueryParser &qp, ::rust::Str field, ::rust::Str prefix) noexcept {
  void (*add_boolean_prefix$)(::Xapian::QueryParser &, ::rust::Str, ::rust::Str) = ::add_boolean_prefix;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_boolean_prefix$(qp, field, prefix);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_rangeprocessor(::Xapian::QueryParser &qp, ::Xapian::RangeProcessor &range_proc) noexcept {
  void (*add_rangeprocessor$)(::Xapian::QueryParser &, ::Xapian::RangeProcessor &) = ::add_rangeprocessor;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_rangeprocessor$(qp, range_proc);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_number_rangeprocessor(::Xapian::QueryParser &qp, ::Xapian::NumberRangeProcessor &range_proc) noexcept {
  void (*add_number_rangeprocessor$)(::Xapian::QueryParser &, ::Xapian::NumberRangeProcessor &) = ::add_number_rangeprocessor;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_number_rangeprocessor$(qp, range_proc);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$parse_query(::Xapian::QueryParser &qp, ::rust::Str query_string, ::std::int32_t flags, ::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*parse_query$)(::Xapian::QueryParser &, ::rust::Str, ::std::int32_t) = ::parse_query;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(parse_query$(qp, query_string, flags).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$parse_query_with_prefix(::Xapian::QueryParser &qp, ::rust::Str query_string, ::std::int32_t flags, ::rust::Str prefix, ::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*parse_query_with_prefix$)(::Xapian::QueryParser &, ::rust::Str, ::std::int32_t, ::rust::Str) = ::parse_query_with_prefix;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(parse_query_with_prefix$(qp, query_string, flags, prefix).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_query(::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*new_query$)() = ::new_query;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(new_query$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_query_range(::std::int32_t op, ::std::uint32_t slot, double begin, double end, ::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*new_query_range$)(::std::int32_t, ::std::uint32_t, double, double) = ::new_query_range;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(new_query_range$(op, slot, begin, end).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_right_query(::Xapian::Query &this_q, ::std::int32_t op, ::Xapian::Query &q, ::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*add_right_query$)(::Xapian::Query &, ::std::int32_t, ::Xapian::Query &) = ::add_right_query;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(add_right_query$(this_q, op, q).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_query_double_with_prefix(::rust::Str prefix, double d, ::Xapian::Query **return$) noexcept {
  ::std::unique_ptr<::Xapian::Query> (*new_query_double_with_prefix$)(::rust::Str, double) = ::new_query_double_with_prefix;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::Query *(new_query_double_with_prefix$(prefix, d).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

bool cxxbridge1$query_is_empty(::Xapian::Query &this_q) noexcept {
  bool (*query_is_empty$)(::Xapian::Query &) = ::query_is_empty;
  return query_is_empty$(this_q);
}

void cxxbridge1$get_description(::Xapian::Query &this_q, ::rust::String *return$) noexcept {
  ::rust::String (*get_description$)(::Xapian::Query &) = ::get_description;
  new (return$) ::rust::String(get_description$(this_q));
}

::rust::repr::PtrLen cxxbridge1$new_multi_value_key_maker(::Xapian::MultiValueKeyMaker **return$) noexcept {
  ::std::unique_ptr<::Xapian::MultiValueKeyMaker> (*new_multi_value_key_maker$)() = ::new_multi_value_key_maker;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::MultiValueKeyMaker *(new_multi_value_key_maker$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$add_value_to_multi_value_key_maker(::Xapian::MultiValueKeyMaker &this_m, ::std::uint32_t slot, bool asc_desc) noexcept {
  void (*add_value_to_multi_value_key_maker$)(::Xapian::MultiValueKeyMaker &, ::std::uint32_t, bool) = ::add_value_to_multi_value_key_maker;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        add_value_to_multi_value_key_maker$(this_m, slot, asc_desc);
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_value_count_match_spy(::std::uint32_t slot, ::Xapian::ValueCountMatchSpy **return$) noexcept {
  ::std::unique_ptr<::Xapian::ValueCountMatchSpy> (*new_value_count_match_spy$)(::std::uint32_t) = ::new_value_count_match_spy;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::ValueCountMatchSpy *(new_value_count_match_spy$(slot).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_range_processor(::std::uint32_t slot, ::rust::Str prefix, ::std::int32_t flags, ::Xapian::RangeProcessor **return$) noexcept {
  ::std::unique_ptr<::Xapian::RangeProcessor> (*new_range_processor$)(::std::uint32_t, ::rust::Str, ::std::int32_t) = ::new_range_processor;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::RangeProcessor *(new_range_processor$(slot, prefix, flags).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_number_range_processor(::std::uint32_t slot, ::rust::Str prefix, ::std::int32_t flags, ::Xapian::NumberRangeProcessor **return$) noexcept {
  ::std::unique_ptr<::Xapian::NumberRangeProcessor> (*new_number_range_processor$)(::std::uint32_t, ::rust::Str, ::std::int32_t) = ::new_number_range_processor;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::NumberRangeProcessor *(new_number_range_processor$(slot, prefix, flags).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$value_count_matchspy_values_begin(::Xapian::ValueCountMatchSpy &vcms, ::Xapian::TermIterator **return$) noexcept {
  ::std::unique_ptr<::Xapian::TermIterator> (*value_count_matchspy_values_begin$)(::Xapian::ValueCountMatchSpy &) = ::value_count_matchspy_values_begin;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::TermIterator *(value_count_matchspy_values_begin$(vcms).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$value_count_matchspy_values_end(::Xapian::ValueCountMatchSpy &vcms, ::Xapian::TermIterator **return$) noexcept {
  ::std::unique_ptr<::Xapian::TermIterator> (*value_count_matchspy_values_end$)(::Xapian::ValueCountMatchSpy &) = ::value_count_matchspy_values_end;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::TermIterator *(value_count_matchspy_values_end$(vcms).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::std::int32_t cxxbridge1$value_count_matchspy_get_total(::Xapian::ValueCountMatchSpy &vcms) noexcept {
  ::std::int32_t (*value_count_matchspy_get_total$)(::Xapian::ValueCountMatchSpy &) = ::value_count_matchspy_get_total;
  return value_count_matchspy_get_total$(vcms);
}

void cxxbridge1$term_iterator_get_termfreq_value(::Xapian::TermIterator &titer, ::rust::String *return$) noexcept {
  ::rust::String (*term_iterator_get_termfreq_value$)(::Xapian::TermIterator &) = ::term_iterator_get_termfreq_value;
  new (return$) ::rust::String(term_iterator_get_termfreq_value$(titer));
}

::std::int32_t cxxbridge1$term_iterator_get_termfreq_freq(::Xapian::TermIterator &titer) noexcept {
  ::std::int32_t (*term_iterator_get_termfreq_freq$)(::Xapian::TermIterator &) = ::term_iterator_get_termfreq_freq;
  return term_iterator_get_termfreq_freq$(titer);
}

bool cxxbridge1$term_iterator_eq(::Xapian::TermIterator &titer, ::Xapian::TermIterator &other) noexcept {
  bool (*term_iterator_eq$)(::Xapian::TermIterator &, ::Xapian::TermIterator &) = ::term_iterator_eq;
  return term_iterator_eq$(titer, other);
}

void cxxbridge1$term_iterator_next(::Xapian::TermIterator &titer) noexcept {
  void (*term_iterator_next$)(::Xapian::TermIterator &) = ::term_iterator_next;
  term_iterator_next$(titer);
}

::rust::repr::PtrLen cxxbridge1$new_bool_weight(::Xapian::BoolWeight **return$) noexcept {
  ::std::unique_ptr<::Xapian::BoolWeight> (*new_bool_weight$)() = ::new_bool_weight;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::BoolWeight *(new_bool_weight$().release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

::rust::repr::PtrLen cxxbridge1$new_bm25_weight(double k1, double k2, double k3, double b, double min_normlen, ::Xapian::BM25Weight **return$) noexcept {
  ::std::unique_ptr<::Xapian::BM25Weight> (*new_bm25_weight$)(double, double, double, double, double) = ::new_bm25_weight;
  ::rust::repr::PtrLen throw$;
  ::rust::behavior::trycatch(
      [&] {
        new (return$) ::Xapian::BM25Weight *(new_bm25_weight$(k1, k2, k3, b, min_normlen).release());
        throw$.ptr = nullptr;
      },
      ::rust::detail::Fail(throw$));
  return throw$;
}

static_assert(::rust::detail::is_complete<::Xapian::Database>::value, "definition of `::Xapian::Database` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::Database>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::Database>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$Database$null(::std::unique_ptr<::Xapian::Database> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Database>();
}
void cxxbridge1$unique_ptr$Xapian$Database$raw(::std::unique_ptr<::Xapian::Database> *ptr, ::Xapian::Database *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Database>(raw);
}
::Xapian::Database const *cxxbridge1$unique_ptr$Xapian$Database$get(::std::unique_ptr<::Xapian::Database> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::Database *cxxbridge1$unique_ptr$Xapian$Database$release(::std::unique_ptr<::Xapian::Database> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$Database$drop(::std::unique_ptr<::Xapian::Database> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::Database>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::Enquire>::value, "definition of `::Xapian::Enquire` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::Enquire>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::Enquire>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$Enquire$null(::std::unique_ptr<::Xapian::Enquire> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Enquire>();
}
void cxxbridge1$unique_ptr$Xapian$Enquire$raw(::std::unique_ptr<::Xapian::Enquire> *ptr, ::Xapian::Enquire *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Enquire>(raw);
}
::Xapian::Enquire const *cxxbridge1$unique_ptr$Xapian$Enquire$get(::std::unique_ptr<::Xapian::Enquire> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::Enquire *cxxbridge1$unique_ptr$Xapian$Enquire$release(::std::unique_ptr<::Xapian::Enquire> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$Enquire$drop(::std::unique_ptr<::Xapian::Enquire> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::Enquire>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::Stem>::value, "definition of `::Xapian::Stem` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::Stem>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::Stem>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$Stem$null(::std::unique_ptr<::Xapian::Stem> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Stem>();
}
void cxxbridge1$unique_ptr$Xapian$Stem$raw(::std::unique_ptr<::Xapian::Stem> *ptr, ::Xapian::Stem *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Stem>(raw);
}
::Xapian::Stem const *cxxbridge1$unique_ptr$Xapian$Stem$get(::std::unique_ptr<::Xapian::Stem> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::Stem *cxxbridge1$unique_ptr$Xapian$Stem$release(::std::unique_ptr<::Xapian::Stem> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$Stem$drop(::std::unique_ptr<::Xapian::Stem> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::Stem>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::WritableDatabase>::value, "definition of `::Xapian::WritableDatabase` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::WritableDatabase>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::WritableDatabase>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$WritableDatabase$null(::std::unique_ptr<::Xapian::WritableDatabase> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::WritableDatabase>();
}
void cxxbridge1$unique_ptr$Xapian$WritableDatabase$raw(::std::unique_ptr<::Xapian::WritableDatabase> *ptr, ::Xapian::WritableDatabase *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::WritableDatabase>(raw);
}
::Xapian::WritableDatabase const *cxxbridge1$unique_ptr$Xapian$WritableDatabase$get(::std::unique_ptr<::Xapian::WritableDatabase> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::WritableDatabase *cxxbridge1$unique_ptr$Xapian$WritableDatabase$release(::std::unique_ptr<::Xapian::WritableDatabase> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$WritableDatabase$drop(::std::unique_ptr<::Xapian::WritableDatabase> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::WritableDatabase>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::TermGenerator>::value, "definition of `::Xapian::TermGenerator` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::TermGenerator>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::TermGenerator>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$TermGenerator$null(::std::unique_ptr<::Xapian::TermGenerator> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::TermGenerator>();
}
void cxxbridge1$unique_ptr$Xapian$TermGenerator$raw(::std::unique_ptr<::Xapian::TermGenerator> *ptr, ::Xapian::TermGenerator *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::TermGenerator>(raw);
}
::Xapian::TermGenerator const *cxxbridge1$unique_ptr$Xapian$TermGenerator$get(::std::unique_ptr<::Xapian::TermGenerator> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::TermGenerator *cxxbridge1$unique_ptr$Xapian$TermGenerator$release(::std::unique_ptr<::Xapian::TermGenerator> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$TermGenerator$drop(::std::unique_ptr<::Xapian::TermGenerator> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::TermGenerator>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::Document>::value, "definition of `::Xapian::Document` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::Document>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::Document>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$Document$null(::std::unique_ptr<::Xapian::Document> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Document>();
}
void cxxbridge1$unique_ptr$Xapian$Document$raw(::std::unique_ptr<::Xapian::Document> *ptr, ::Xapian::Document *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Document>(raw);
}
::Xapian::Document const *cxxbridge1$unique_ptr$Xapian$Document$get(::std::unique_ptr<::Xapian::Document> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::Document *cxxbridge1$unique_ptr$Xapian$Document$release(::std::unique_ptr<::Xapian::Document> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$Document$drop(::std::unique_ptr<::Xapian::Document> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::Document>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::MSetIterator>::value, "definition of `::Xapian::MSetIterator` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::MSetIterator>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::MSetIterator>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$MSetIterator$null(::std::unique_ptr<::Xapian::MSetIterator> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MSetIterator>();
}
void cxxbridge1$unique_ptr$Xapian$MSetIterator$raw(::std::unique_ptr<::Xapian::MSetIterator> *ptr, ::Xapian::MSetIterator *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MSetIterator>(raw);
}
::Xapian::MSetIterator const *cxxbridge1$unique_ptr$Xapian$MSetIterator$get(::std::unique_ptr<::Xapian::MSetIterator> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::MSetIterator *cxxbridge1$unique_ptr$Xapian$MSetIterator$release(::std::unique_ptr<::Xapian::MSetIterator> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$MSetIterator$drop(::std::unique_ptr<::Xapian::MSetIterator> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::MSetIterator>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::MSet>::value, "definition of `::Xapian::MSet` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::MSet>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::MSet>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$MSet$null(::std::unique_ptr<::Xapian::MSet> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MSet>();
}
void cxxbridge1$unique_ptr$Xapian$MSet$raw(::std::unique_ptr<::Xapian::MSet> *ptr, ::Xapian::MSet *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MSet>(raw);
}
::Xapian::MSet const *cxxbridge1$unique_ptr$Xapian$MSet$get(::std::unique_ptr<::Xapian::MSet> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::MSet *cxxbridge1$unique_ptr$Xapian$MSet$release(::std::unique_ptr<::Xapian::MSet> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$MSet$drop(::std::unique_ptr<::Xapian::MSet> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::MSet>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::QueryParser>::value, "definition of `::Xapian::QueryParser` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::QueryParser>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::QueryParser>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$QueryParser$null(::std::unique_ptr<::Xapian::QueryParser> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::QueryParser>();
}
void cxxbridge1$unique_ptr$Xapian$QueryParser$raw(::std::unique_ptr<::Xapian::QueryParser> *ptr, ::Xapian::QueryParser *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::QueryParser>(raw);
}
::Xapian::QueryParser const *cxxbridge1$unique_ptr$Xapian$QueryParser$get(::std::unique_ptr<::Xapian::QueryParser> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::QueryParser *cxxbridge1$unique_ptr$Xapian$QueryParser$release(::std::unique_ptr<::Xapian::QueryParser> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$QueryParser$drop(::std::unique_ptr<::Xapian::QueryParser> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::QueryParser>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::Query>::value, "definition of `::Xapian::Query` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::Query>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::Query>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$Query$null(::std::unique_ptr<::Xapian::Query> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Query>();
}
void cxxbridge1$unique_ptr$Xapian$Query$raw(::std::unique_ptr<::Xapian::Query> *ptr, ::Xapian::Query *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::Query>(raw);
}
::Xapian::Query const *cxxbridge1$unique_ptr$Xapian$Query$get(::std::unique_ptr<::Xapian::Query> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::Query *cxxbridge1$unique_ptr$Xapian$Query$release(::std::unique_ptr<::Xapian::Query> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$Query$drop(::std::unique_ptr<::Xapian::Query> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::Query>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::MultiValueKeyMaker>::value, "definition of `::Xapian::MultiValueKeyMaker` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::MultiValueKeyMaker>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::MultiValueKeyMaker>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$MultiValueKeyMaker$null(::std::unique_ptr<::Xapian::MultiValueKeyMaker> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MultiValueKeyMaker>();
}
void cxxbridge1$unique_ptr$Xapian$MultiValueKeyMaker$raw(::std::unique_ptr<::Xapian::MultiValueKeyMaker> *ptr, ::Xapian::MultiValueKeyMaker *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::MultiValueKeyMaker>(raw);
}
::Xapian::MultiValueKeyMaker const *cxxbridge1$unique_ptr$Xapian$MultiValueKeyMaker$get(::std::unique_ptr<::Xapian::MultiValueKeyMaker> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::MultiValueKeyMaker *cxxbridge1$unique_ptr$Xapian$MultiValueKeyMaker$release(::std::unique_ptr<::Xapian::MultiValueKeyMaker> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$MultiValueKeyMaker$drop(::std::unique_ptr<::Xapian::MultiValueKeyMaker> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::MultiValueKeyMaker>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::ValueCountMatchSpy>::value, "definition of `::Xapian::ValueCountMatchSpy` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::ValueCountMatchSpy>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::ValueCountMatchSpy>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$ValueCountMatchSpy$null(::std::unique_ptr<::Xapian::ValueCountMatchSpy> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::ValueCountMatchSpy>();
}
void cxxbridge1$unique_ptr$Xapian$ValueCountMatchSpy$raw(::std::unique_ptr<::Xapian::ValueCountMatchSpy> *ptr, ::Xapian::ValueCountMatchSpy *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::ValueCountMatchSpy>(raw);
}
::Xapian::ValueCountMatchSpy const *cxxbridge1$unique_ptr$Xapian$ValueCountMatchSpy$get(::std::unique_ptr<::Xapian::ValueCountMatchSpy> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::ValueCountMatchSpy *cxxbridge1$unique_ptr$Xapian$ValueCountMatchSpy$release(::std::unique_ptr<::Xapian::ValueCountMatchSpy> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$ValueCountMatchSpy$drop(::std::unique_ptr<::Xapian::ValueCountMatchSpy> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::ValueCountMatchSpy>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::RangeProcessor>::value, "definition of `::Xapian::RangeProcessor` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::RangeProcessor>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::RangeProcessor>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$RangeProcessor$null(::std::unique_ptr<::Xapian::RangeProcessor> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::RangeProcessor>();
}
void cxxbridge1$unique_ptr$Xapian$RangeProcessor$raw(::std::unique_ptr<::Xapian::RangeProcessor> *ptr, ::Xapian::RangeProcessor *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::RangeProcessor>(raw);
}
::Xapian::RangeProcessor const *cxxbridge1$unique_ptr$Xapian$RangeProcessor$get(::std::unique_ptr<::Xapian::RangeProcessor> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::RangeProcessor *cxxbridge1$unique_ptr$Xapian$RangeProcessor$release(::std::unique_ptr<::Xapian::RangeProcessor> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$RangeProcessor$drop(::std::unique_ptr<::Xapian::RangeProcessor> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::RangeProcessor>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::NumberRangeProcessor>::value, "definition of `::Xapian::NumberRangeProcessor` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::NumberRangeProcessor>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::NumberRangeProcessor>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$NumberRangeProcessor$null(::std::unique_ptr<::Xapian::NumberRangeProcessor> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::NumberRangeProcessor>();
}
void cxxbridge1$unique_ptr$Xapian$NumberRangeProcessor$raw(::std::unique_ptr<::Xapian::NumberRangeProcessor> *ptr, ::Xapian::NumberRangeProcessor *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::NumberRangeProcessor>(raw);
}
::Xapian::NumberRangeProcessor const *cxxbridge1$unique_ptr$Xapian$NumberRangeProcessor$get(::std::unique_ptr<::Xapian::NumberRangeProcessor> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::NumberRangeProcessor *cxxbridge1$unique_ptr$Xapian$NumberRangeProcessor$release(::std::unique_ptr<::Xapian::NumberRangeProcessor> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$NumberRangeProcessor$drop(::std::unique_ptr<::Xapian::NumberRangeProcessor> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::NumberRangeProcessor>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::TermIterator>::value, "definition of `::Xapian::TermIterator` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::TermIterator>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::TermIterator>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$TermIterator$null(::std::unique_ptr<::Xapian::TermIterator> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::TermIterator>();
}
void cxxbridge1$unique_ptr$Xapian$TermIterator$raw(::std::unique_ptr<::Xapian::TermIterator> *ptr, ::Xapian::TermIterator *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::TermIterator>(raw);
}
::Xapian::TermIterator const *cxxbridge1$unique_ptr$Xapian$TermIterator$get(::std::unique_ptr<::Xapian::TermIterator> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::TermIterator *cxxbridge1$unique_ptr$Xapian$TermIterator$release(::std::unique_ptr<::Xapian::TermIterator> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$TermIterator$drop(::std::unique_ptr<::Xapian::TermIterator> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::TermIterator>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::BoolWeight>::value, "definition of `::Xapian::BoolWeight` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::BoolWeight>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::BoolWeight>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$BoolWeight$null(::std::unique_ptr<::Xapian::BoolWeight> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::BoolWeight>();
}
void cxxbridge1$unique_ptr$Xapian$BoolWeight$raw(::std::unique_ptr<::Xapian::BoolWeight> *ptr, ::Xapian::BoolWeight *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::BoolWeight>(raw);
}
::Xapian::BoolWeight const *cxxbridge1$unique_ptr$Xapian$BoolWeight$get(::std::unique_ptr<::Xapian::BoolWeight> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::BoolWeight *cxxbridge1$unique_ptr$Xapian$BoolWeight$release(::std::unique_ptr<::Xapian::BoolWeight> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$BoolWeight$drop(::std::unique_ptr<::Xapian::BoolWeight> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::BoolWeight>::value>{}(ptr);
}

static_assert(::rust::detail::is_complete<::Xapian::BM25Weight>::value, "definition of `::Xapian::BM25Weight` is required");
static_assert(sizeof(::std::unique_ptr<::Xapian::BM25Weight>) == sizeof(void *), "");
static_assert(alignof(::std::unique_ptr<::Xapian::BM25Weight>) == alignof(void *), "");
void cxxbridge1$unique_ptr$Xapian$BM25Weight$null(::std::unique_ptr<::Xapian::BM25Weight> *ptr) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::BM25Weight>();
}
void cxxbridge1$unique_ptr$Xapian$BM25Weight$raw(::std::unique_ptr<::Xapian::BM25Weight> *ptr, ::Xapian::BM25Weight *raw) noexcept {
  ::new (ptr) ::std::unique_ptr<::Xapian::BM25Weight>(raw);
}
::Xapian::BM25Weight const *cxxbridge1$unique_ptr$Xapian$BM25Weight$get(::std::unique_ptr<::Xapian::BM25Weight> const &ptr) noexcept {
  return ptr.get();
}
::Xapian::BM25Weight *cxxbridge1$unique_ptr$Xapian$BM25Weight$release(::std::unique_ptr<::Xapian::BM25Weight> &ptr) noexcept {
  return ptr.release();
}
void cxxbridge1$unique_ptr$Xapian$BM25Weight$drop(::std::unique_ptr<::Xapian::BM25Weight> *ptr) noexcept {
  ::rust::deleter_if<::rust::detail::is_complete<::Xapian::BM25Weight>::value>{}(ptr);
}
} // extern "C"
