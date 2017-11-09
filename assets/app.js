import Vue from 'vue';
import { send } from './utils.js';
import tpl from './app.html';

export default () => {
  window.app = new Vue({
    el: '#app',
    template: tpl,
    data: {
      query: decodeURIComponent(location.hash.slice(1)) || 'all',
      threads: false,
      tags: {}
    },
    created: function() {
      return this.send('/login', {
        offset: new Date().getTimezoneOffset() / 60
      }).then(() => this.fetch());
    },
    methods: {
      send: send,
      fetch: function(query) {
        if (query) {
          this.query = query;
        }
        window.location.hash = this.query;
        this.$nextTick(() => {
          this.send('/tags')
            .then(res => (this.tags = res))
            .then(() => this.$refs.msgs.fetch());
        });
      },
      searchHeader: function(name, value) {
        return this.fetch('header ' + name + ' "' + value + '"');
      },
      searchTag: function(tag) {
        return this.fetch('keyword ' + tag);
      }
    }
  });
};
