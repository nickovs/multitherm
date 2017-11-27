Vue.component('thermostat', {
    props: ['todo'],
    template: '<div><p class="roomname">{{ todo.roomname }}</p><p class="currenttemp">{{ todo.t }}</p><p class="setpoint">{{ todo.set }}</p></div>'
})


var thermo_app = new Vue({
    el: '#thermostats',
    data: {
        states: [
            { ID:3,
              board_id: 3,
              index: 5,
              roomname: 'Kitchen',
              adj: 0.0,
              chan: 5,
              out: 1,
              override: 1,
              set: 24.0,
              t: 20.9},
            { id: 0, roomname: 'Vegetables', set: 24.0, t: 20.9 }
        ]
    },
    created: function() {
        axios.get("http://thermostat.local:27315/thermostats/all_states")
            .then(function(response) {
                console.log(response);
                console.log(response.data);
                this.states = response.data;
            })
            .catch(function (error) {
                console.log(error);
            });
    }
})
